from nbformat import write as nbwrite
from nbformat.v4 import new_code_cell
from nbformat.v4 import new_markdown_cell
from nbformat.v4 import new_notebook
import re
import sys


MODULE_REGEX = r'^[_a-zA-Z][_a-zA-Z0-9]+$'

module_name = '{{cookiecutter.module_name}}'

if not re.match(MODULE_REGEX, module_name):
    print('ERROR: %s is not a valid Python module name!' % module_name)

    # exits with status 1 to indicate failure
    sys.exit(1)


notebook_cells = [
new_markdown_cell("""\
## Required setup

Run this cell first"""),

new_code_cell("""\
import logging
import xun

logging.basicConfig(level=logging.WARNING)
logging.getLogger('xun').setLevel(logging.DEBUG)

# Add any paths to xun function collections here.
xun.init_notebook(repositories=[
    '/paths/to/my/xun/modules/collection/',
    ...
])"""),

new_markdown_cell("""\
# {{cookiecutter.module_name}}

Description"""),

new_markdown_cell("""\
## Configuration"""),

new_markdown_cell("""\
### Driver setup

Set up the xun driver. It is responsible for..."""),

new_code_cell("""\
driver = xun.functions.driver.Sequential()"""),

new_markdown_cell("""\
### Store setup

Set up the xun store."""),

new_code_cell("""\
store = xun.functions.store.Memory()"""),

new_markdown_cell("""\
## Workflow"""),

new_code_cell("""\
from {{cookiecutter.module_name}} import capitalize"""),

new_code_cell("""\
@xun.function()
def entry_point_workflow(name):
    print(f'Hello {capitalized_name}')
    with ...:
        \"\"\"Set up your workflow here\"\"\"
        capitalized_name = capitalize(name)"""),

new_code_cell("""\
entry_point_workflow.blueprint(\"world\").run(driver=driver, store=store)"""),
]


def create_jupyter_notebook():
    notebook_fname = '{{cookiecutter.module_name}}.ipynb'

    nb = new_notebook()
    nb['cells'] = notebook_cells

    with open(notebook_fname, 'w') as f:
        nbwrite(nb, f)


create_jupyter_notebook()
