import asyncio
import logging
import os
from typing import List, Optional
from app.services.providers.base import BaseProvider, SearchResult
from app.schemas.models import SongMetadata
from app.services.providers.qq import QQMusicProvider
from app.services.providers.kugou import KugouProvider
from app.services.providers.netease import NeteaseProvider

logger = logging.getLogger(__name__)


def _is_enabled(env_var: str, default: bool = True) -> bool:
    """Check if a provider is enabled via environment variable."""
    value = os.getenv(env_var, str(default)).lower()
    return value in ("true", "1", "yes", "on")


class Aggregator:
    def __init__(self):
        self.providers: List[BaseProvider] = []
        
        # Conditionally register providers based on environment variables
        if _is_enabled("ENABLE_QQ"):
            self.providers.append(QQMusicProvider())
            logger.info("QQ Music provider enabled")
        else:
            logger.info("QQ Music provider disabled")
            
        if _is_enabled("ENABLE_KUGOU"):
            self.providers.append(KugouProvider())
            logger.info("Kugou provider enabled")
        else:
            logger.info("Kugou provider disabled")
            
        if _is_enabled("ENABLE_NETEASE"):
            self.providers.append(NeteaseProvider())
            logger.info("Netease provider enabled")
        else:
            logger.info("Netease provider disabled")
        
        if not self.providers:
            logger.warning("No providers enabled! At least one ENABLE_* env var should be True.")

    async def search_all(self, metadata: SongMetadata) -> List[SearchResult]:
        """
        并发执行所有搜索策略（严谨搜索、模糊搜索、兜底搜索）。
        """
        search_tasks = []

        # 策略 1: 原始元数据 (Strict)
        search_tasks.append(self._execute_search(metadata))
        
        # 策略 2: 简化艺人名 (Simplified Artist)
        simple_artist = self._simplify_artist(metadata.artist)
        if simple_artist != metadata.artist and simple_artist:
            new_meta = metadata.model_copy(update={"artist": simple_artist})
            search_tasks.append(self._execute_search(new_meta))

        # 策略 3: 仅歌名 (Title Only)
        # 注意：已注释以减少搜索开销，提升响应速度
        # 如需更宽泛的匹配，可取消注释
        # if metadata.title:
        #     title_meta = metadata.model_copy(update={"artist": ""})
        #     search_tasks.append(self._execute_search(title_meta))

        # 并发执行所有策略
        logger.info(f"Firing {len(search_tasks)} search strategies concurrently...")
        strategies_results = await asyncio.gather(*search_tasks)
        
        # 结果合并与去重
        seen_ids = set()
        final_results = []
        
        for strategy_res in strategies_results:
            if not strategy_res: continue
            for res in strategy_res:
                # 唯一键：平台_歌曲ID
                unique_key = f"{res.provider}_{res.id}"
                if unique_key not in seen_ids:
                    seen_ids.add(unique_key)
                    final_results.append(res)
        
        logger.info(f"Concurrency search finished. Total unique candidates: {len(final_results)}")
        return final_results

    async def _execute_search(self, metadata: SongMetadata) -> List[SearchResult]:
        """
        内部函数：并发调用所有 Enabled 的 Provider 进行搜索，并应用差异化超时。
        """
        
        async def search_with_timeout(provider: BaseProvider) -> List[SearchResult]:
            # --- 关键优化：差异化超时 ---
            # 国内源（QQ/网易）通常很快，给 15s 作为兜底
            timeout = 15.0
            
            try:
                # 使用 asyncio.wait_for 强制超时
                return await asyncio.wait_for(provider.search(metadata), timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning(f"Provider {provider.provider_name} timed out after {timeout}s")
                return []
            except Exception as e:
                logger.error(f"Provider {provider.provider_name} search failed: {e}")
                return []

        # 创建并发任务
        tasks = [search_with_timeout(provider) for provider in self.providers]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)
        
        all_results = []
        for result in results_list:
            if isinstance(result, list):
                all_results.extend(result)
            # 注意：由于我们在 search_with_timeout 里捕获了 Exception，
            # 这里的 result 理论上只会是 list。但在极个别情况下做个类型检查更安全。
            
        return all_results

    def _simplify_artist(self, artist: str) -> str:
        if not artist: return ""
        # Take first part before common separators
        separators = ["&", ",", ";", " feat.", " ft.", " vs.", " x "]
        cleaned = artist
        for sep in separators:
            if sep in cleaned:
                cleaned = cleaned.split(sep)[0]
        return cleaned.strip()

    async def fetch_lyric(self, provider_name: str, song_id: str, **kwargs) -> Optional[bytes]:
        """
        Fetch lyric content from a specific provider.
        """
        provider = next((p for p in self.providers if p.provider_name == provider_name), None)
        if not provider:
            logger.error(f"Provider not found: {provider_name}")
            return None
            
        # Retry mechanism to ensure reliable fetching (especially for Top Candidate)
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # 10s timeout per attempt
                return await asyncio.wait_for(provider.get_lyric_content(song_id, **kwargs), timeout=10.0)
            except asyncio.TimeoutError as e:
                last_error = e
                logger.warning(f"Fetch lyric from {provider_name} (ID: {song_id}) timed out (Attempt {attempt+1}/{max_retries})")
            except Exception as e:
                last_error = e
                logger.warning(f"Failed to fetch lyric from {provider_name} (ID: {song_id}): {e} (Attempt {attempt+1}/{max_retries})")
            
            # Backoff before retry
            if attempt < max_retries - 1:
                await asyncio.sleep(0.5)
                
        logger.error(f"Given up fetching lyric from {provider_name} (ID: {song_id}) after {max_retries} attempts.")
        return None
