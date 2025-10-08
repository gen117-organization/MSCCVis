from pathlib import Path
import sys

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

import modules.identify_microservice
import modules.map_file
import modules.select_project


if __name__ == "__main__":
    modules.identify_microservice.analyze_dataset()
    modules.map_file.map_file()
    modules.select_project.select_project()