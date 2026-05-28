from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MacroConfig:
    dry_run: bool = True
    capcut_executable_path: str = ""
    typecast_url: str = "https://typecast.ai/"
    wait_seconds: float = 1.0
    hotkeys: dict[str, tuple[str, ...]] = field(
        default_factory=lambda: {
            "paste": ("ctrl", "v"),
            "select_all": ("ctrl", "a"),
            "save": ("ctrl", "s"),
        }
    )
    coordinates: dict[str, tuple[int, int]] = field(
        default_factory=lambda: {
            "typecast_text_area": (0, 0),
            "typecast_generate_button": (0, 0),
            "capcut_import_button": (0, 0),
            "capcut_export_button": (0, 0),
        }
    )


DEFAULT_CONFIG = MacroConfig()
