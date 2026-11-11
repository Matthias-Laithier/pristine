CONTRACT = "dev:\n\t./run\ncheck:\n\tpytest\ncheck-all: check\nbuild:\n\tdocker build .\n"
APPLICATION: dict[str, str] = {
    "Makefile": CONTRACT,
    "Dockerfile": "FROM python\n",
}
