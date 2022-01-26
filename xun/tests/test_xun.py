import xun


def test_tagged_stores():
    driver = xun.functions.driver.Sequential()
    store = xun.functions.store.Memory()

    @xun.function(custom_tag='hello {1}!')
    def f(a, b):
        pass

    @xun.function()
    def main():
        with ...:
            f(1, 'argument')

    main.blueprint().run(driver=driver, store=store)

    main_tags = store.tags[main.callnode()]
    f_tags = store.tags[f.callnode(1, 'argument')]

    assert set(main_tags.keys()) == {
        'created_by',
        'entry_point',
        'function_name',
        'start_time',
        'timestamp',
    }

    assert set(f_tags.keys()) == {
        'created_by',
        'custom_tag',
        'entry_point',
        'function_name',
        'start_time',
        'timestamp',
    }

    assert main_tags['entry_point'] == 'main'
    assert main_tags['function_name'] == 'main'

    assert f_tags['entry_point'] == 'main'
    assert f_tags['function_name'] == 'f'
    assert f_tags['custom_tag'] == 'hello argument!'
