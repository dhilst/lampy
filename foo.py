#!/Users/gecko/code/lampycode/let.py

# let f = let n f in
#         1 if n == 0 else n * f(n - 1, f)
#     in f(5, f)
#


let def fact a in let match a in 0 => 1 | n => n + 1 end in
    print(fact(5))
