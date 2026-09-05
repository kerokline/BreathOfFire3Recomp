# list_programs.py -- Ghidra script (PyGhidra): print every program in the
# project as "PROG <path> <content type>". Headless needs SOME program to
# -process, so tools/ghidra_run.py runs this against the boot EXE read-only.
# @category PSXRecomp

root = state.getProject().getProjectData().getRootFolder()


def walk(folder):
    for f in folder.getFiles():
        print("PROG %s %s" % (f.getPathname(), f.getContentType()))
    for sub in folder.getFolders():
        walk(sub)


walk(root)
print("PROG_CURRENT %s funcs=%d base=%s" % (
    currentProgram.getName(), currentProgram.getFunctionManager().getFunctionCount(),
    currentProgram.getImageBase()))
