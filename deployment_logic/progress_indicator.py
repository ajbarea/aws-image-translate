"""
Provides progress indication and colored terminal output for the deployment script.
"""


class Colors:
    """ANSI color codes for terminal output"""

    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


class ProgressIndicator:
    """Simple progress indicator for deployment steps"""

    def __init__(self, total_steps: int):
        self.total_steps = total_steps
        self.current_step = 0

    def next_step(self, description: str):
        self.current_step += 1
        print(
            f"\n{Colors.OKBLUE}[{self.current_step}/{self.total_steps}] {description}{Colors.ENDC}"
        )

    def success(self, message: str):
        print(f"{Colors.OKGREEN}[OK] {message}{Colors.ENDC}")

    def warning(self, message: str):
        print(f"{Colors.WARNING}[WARNING] {message}{Colors.ENDC}")

    def error(self, message: str):
        print(f"{Colors.FAIL}[ERROR] {message}{Colors.ENDC}")

    def info(self, message: str):
        print(f"{Colors.OKCYAN}[INFO] {message}{Colors.ENDC}")
