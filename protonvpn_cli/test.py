def get_place(value, list):
    """Returns position of value in array"""
    for i, j in enumerate(list):
        if j == value:
            return i + 1

list = list(range(15))
print(get_place(10, list))
print(list)
print(list[get_place(10, list)])
