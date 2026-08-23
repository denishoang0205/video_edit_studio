"""Service Layer: Video Engine, Drive Manager, and Automation Adapters."""
from src.services.video_engine import get_video_duration, process_video_custom, split_video_custom
from src.services.drive_service import (
    scan_source_directory, scan_finished_results, load_history, save_history,
    delete_finished_result, delete_all_finished_results,
    get_publishing_matrix, toggle_publishing_clip_status, change_account_target_channel, batch_toggle_publishing_clips,
    load_accounts_data, save_accounts_data, ensure_channel_folders,
    load_settings, save_settings
)
from src.services.adspower_service import (
    check_adspower_status, get_adspower_profiles, start_adspower_browser, stop_adspower_browser, is_browser_active
)
from src.services.hma_service import (
    find_hma_executable, get_current_public_ip, connect_hma, change_ip_hma, disconnect_hma
)
from src.services.tiktok_uploader import upload_video_to_tiktok_cdp

__all__ = [
    "get_video_duration", "process_video_custom", "split_video_custom",
    "scan_source_directory", "scan_finished_results", "load_history", "save_history",
    "delete_finished_result", "delete_all_finished_results",
    "get_publishing_matrix", "toggle_publishing_clip_status", "change_account_target_channel", "batch_toggle_publishing_clips",
    "load_accounts_data", "save_accounts_data", "ensure_channel_folders",
    "load_settings", "save_settings",
    "check_adspower_status", "get_adspower_profiles", "start_adspower_browser", "stop_adspower_browser", "is_browser_active",
    "find_hma_executable", "get_current_public_ip", "connect_hma", "change_ip_hma", "disconnect_hma",
    "upload_video_to_tiktok_cdp"
]
