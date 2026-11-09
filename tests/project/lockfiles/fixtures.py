CONTRACT = "dev:\n\t./run\ncheck:\n\tpytest\ncheck-all: check\nbuild:\n\tdocker build .\naudit:\n\tgovulncheck ./...\n\tnpm audit\n"
APPLICATION: dict[str, str] = {
    "Makefile": CONTRACT,
    "Dockerfile": "FROM python\n",
    "go.mod": "module app\n",
}
