import streamlit.components.v1 as components
import os

# 루트 경로 기준으로 컴포넌트 경로 탐색
base_dir = os.path.dirname(__file__)

editor_path = os.path.join(base_dir, "components", "map_editor")
map_editor_component = components.declare_component("map_editor", path=editor_path)

viewer_path = os.path.join(base_dir, "components", "map_viewer")
map_viewer_component = components.declare_component("map_viewer", path=viewer_path)
