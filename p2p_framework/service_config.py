from p2p_framework.decorators import HandlerAndData


class ThreadGroup:
    def __init__(self, *threads: HandlerAndData):
        self.threads = threads


class ProcessGroup:
    def __init__(self, *processes: HandlerAndData):
        self.processes = processes
