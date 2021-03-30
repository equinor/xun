def init_notebook(repositories=(), _old_repositories=[]):
    from IPython.core.display import display, HTML
    import os
    import sys
    if os.getcwd() in sys.path:
        sys.path.remove(os.getcwd())
    while _old_repositories:
        repo = _old_repositories.pop()
        if repo in sys.path:
            sys.path.remove(repo)
    for repo in repositories:
        if repo not in sys.path:
            sys.path.append(repo)
    _old_repositories.extend(repositories)
    display(HTML('<h1 style="display: inline">☴</h1> xun initialized'))
