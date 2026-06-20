import ctypes
from ctypes import wintypes

# Define constants
TH32CS_SNAPPROCESS = 0x00000002


class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_char * 260),
    ]


def get_running_processes():
    kernel32 = ctypes.windll.kernel32
    hProcessSnap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if hProcessSnap == -1:
        return []

    pe32 = PROCESSENTRY32()
    pe32.dwSize = ctypes.sizeof(PROCESSENTRY32)

    processes = []
    if kernel32.Process32First(hProcessSnap, ctypes.byref(pe32)):
        while True:
            processes.append(pe32.szExeFile.decode('utf-8', 'ignore'))
            if not kernel32.Process32Next(hProcessSnap, ctypes.byref(pe32)):
                break

    kernel32.CloseHandle(hProcessSnap)
    return processes


if __name__ == "__main__":
    import time

    start = time.time()
    procs = get_running_processes()
    duration = (time.time() - start) * 1000
    print(f"Found {len(procs)} processes in {duration:.2f}ms")

    targets = ["cursor.exe", "code.exe", "claude.exe", "antigravity"]
    for p in procs:
        if any(t in p.lower() for t in targets):
            print(f"Found target: {p}")
