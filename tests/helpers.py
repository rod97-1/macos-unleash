import subprocess


class FakeRunner:
    def __init__(self, responses=None, available=None):
        self.responses = responses or {}
        self.available = available or set()
        self.calls = []

    def which(self, name):
        return "/usr/bin/" + name if name in self.available else None

    def run(self, argv, check=True, live=False):
        from unleashlib.runner import CommandError

        self.calls.append(list(argv))
        code, output = self.responses.get(tuple(argv), (0, ""))
        if check and code:
            raise CommandError(argv, code, output)
        return subprocess.CompletedProcess(argv, code, output, "")
