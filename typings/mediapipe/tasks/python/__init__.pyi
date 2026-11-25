from mediapipe.tasks.python import vision as vision

class BaseOptions:
    def __init__(self, model_asset_path: str | None = None) -> None: ...
