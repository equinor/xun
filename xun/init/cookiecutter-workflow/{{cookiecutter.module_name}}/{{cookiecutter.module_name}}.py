import xun


@xun.function()
def capitalize(name):
    return first_letter + trailing_letters
    with ...:
        first_letter = name[0].upper()
        trailing_letters = name[1:]
