#!/Users/gecko/code/lampycode/let.py



let f = let n in let f in
        1 if n == 0 else n * f(n - 1)(f)
    in f(5)(f)
