from .. import filename_from_args
import argparse


def test_filename_from_args():
    args = argparse.Namespace(arg0='arg0', arg1='arg1', arg2='arg2')

    hash = '80d4245367911a8c99df2a50d4eba579c5d2efb3e4560077eb8845a39c4bfbbe'
    result = filename_from_args(args)

    assert result == hash
