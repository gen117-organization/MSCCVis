class FileMapper:
    def __init__(self, files: list, project_dir: str) -> None:
        self.id_to_path = {}
        self.path_to_id = {}
        self.file_loc = {}
        for file in files:
            file_id = int(file["file_id"])
            path = str(file["file_path"]).replace(project_dir+"/", "")
            self.id_to_path[file_id] = path
            self.path_to_id[path] = file_id
            self.file_loc[path] = int(file["loc"])
    
    def get_file_id(self, path: str) -> int:
        return self.path_to_id[path]
    
    def get_file_path(self, file_id: int) -> str:
        return self.id_to_path[file_id]
    
    def get_file_loc(self, path: str) -> int:
        if path not in self.file_loc.keys():
            return -1
        return self.file_loc[path]


def calculate_loc(file_path: str) -> int:
    with open(file_path, "r") as f:
        return len(f.readlines())