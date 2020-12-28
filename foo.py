#!/Users/gecko/code/lampycode/let.py

# let f = let n f in
#         1 if n == 0 else n * f(n - 1, f)
#     in f(5, f)
#


let import math as m, sys in
let def foo a b in a + b in
    print(foo(1, 2) + m.pi)
