import os
import sys
from typing import List, Dict, Any

base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from config import ASSETS_DIR, FONTS_DIR, PRESETS_DIR, DEFAULT_FONT_PATH

SYSTEM_WINDOWS_FONTS_DIR = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts')

class AssetManager:
    """
    Asset Manager for TikTok Studio.
    Supports dynamic font discovery, preset loading, and path resolution.
    """

    @staticmethod
    def get_fonts_dir() -> str:
        os.makedirs(FONTS_DIR, exist_ok=True)
        return FONTS_DIR

    @staticmethod
    def list_fonts() -> List[Dict[str, Any]]:
        fonts = []
        seen_names = set()

        # 1. Custom / Local fonts in assets/fonts/
        if os.path.exists(FONTS_DIR):
            for file in os.listdir(FONTS_DIR):
                if file.lower().endswith(('.ttf', '.otf', '.woff', '.woff2')):
                    font_id = os.path.splitext(file)[0]
                    font_path = os.path.join(FONTS_DIR, file)
                    display_name = font_id.replace('-', ' ').replace('_', ' ')
                    fonts.append({
                        'id': font_id,
                        'name': display_name,
                        'filename': file,
                        'path': font_path,
                        'is_custom': True,
                        'type': 'local_asset'
                    })
                    seen_names.add(font_id.lower())

        # 2. Popular System Fonts
        standard_fonts = [
            {'id': 'Poppins-Bold', 'name': 'Poppins Bold (Modern)', 'file': 'Poppins-Bold.ttf'},
            {'id': 'Arial-Bold', 'name': 'Arial Bold (Classic)', 'file': 'arialbd.ttf'},
            {'id': 'Arial', 'name': 'Arial Standard', 'file': 'arial.ttf'},
            {'id': 'SegoeUI-Bold', 'name': 'Segoe UI Bold', 'file': 'segoeuib.ttf'},
            {'id': 'Tahoma-Bold', 'name': 'Tahoma Bold', 'file': 'tahomabd.ttf'},
            {'id': 'Impact', 'name': 'Impact (Viral Meme)', 'file': 'impact.ttf'},
            {'id': 'Montserrat-Bold', 'name': 'Montserrat Bold', 'file': 'Montserrat-Bold.ttf'},
            {'id': 'BeVietnamPro-Bold', 'name': 'Be Vietnam Pro Bold', 'file': 'BeVietnamPro-Bold.ttf'},
        ]

        for sf in standard_fonts:
            if sf['id'].lower() not in seen_names:
                sys_path = os.path.join(SYSTEM_WINDOWS_FONTS_DIR, sf['file'])
                fonts.append({
                    'id': sf['id'],
                    'name': sf['name'],
                    'filename': sf['file'],
                    'path': sys_path if os.path.exists(sys_path) else None,
                    'is_custom': False,
                    'type': 'system'
                })
                seen_names.add(sf['id'].lower())

        return fonts

    @classmethod
    def resolve_font_path(cls, font_name: str, fallback_path: str = DEFAULT_FONT_PATH) -> str:
        if not font_name:
            return fallback_path if os.path.exists(fallback_path) else ''

        clean_name = font_name.strip()
        candidates = [
            os.path.join(FONTS_DIR, f"{clean_name}.ttf"),
            os.path.join(FONTS_DIR, f"{clean_name}.otf"),
            os.path.join(FONTS_DIR, f"{clean_name}-Bold.ttf"),
            os.path.join(FONTS_DIR, clean_name),
            os.path.join(SYSTEM_WINDOWS_FONTS_DIR, f"{clean_name}.ttf"),
            os.path.join(SYSTEM_WINDOWS_FONTS_DIR, f"{clean_name.lower()}.ttf"),
            os.path.join(SYSTEM_WINDOWS_FONTS_DIR, "arialbd.ttf"),
            os.path.join(SYSTEM_WINDOWS_FONTS_DIR, "arial.ttf"),
            os.path.join(SYSTEM_WINDOWS_FONTS_DIR, "tahomabd.ttf"),
            fallback_path
        ]

        for cand in candidates:
            if cand and os.path.exists(cand):
                return cand

        return fallback_path if os.path.exists(fallback_path) else ''
