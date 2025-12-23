from devrules.config import Config


class BaseCtxBuilder:
    def set_config(self, config: Config):
        self.config = config

    def set_current_branch(self, current_branch: str):
        self.current_branch = current_branch
