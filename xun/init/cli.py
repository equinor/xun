from cookiecutter.main import cookiecutter
import pkg_resources


def main(args):
    template_path = pkg_resources.resource_filename(
        'xun', 'init/cookiecutter-workflow/')
    cookiecutter(template=template_path, output_dir=args.path)
