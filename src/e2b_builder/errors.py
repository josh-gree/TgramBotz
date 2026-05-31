class DockerfileNotFoundError(FileNotFoundError):
    pass


class ContextNotFoundError(FileNotFoundError):
    pass


class BuildError(RuntimeError):
    pass


class RunError(RuntimeError):
    pass
