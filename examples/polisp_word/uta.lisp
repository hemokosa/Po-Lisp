; lambda と label で、言葉をあつかう道具をつくる
; 読み込む:  python3 polisp_word_lambda.py examples/polisp_word/uta.lisp
;   または REPL で  :load examples/polisp_word/uta.lisp

; --- まず、空かどうかを問う道具。eq はアトムしか比べられないので atom で守る
:def null (lambda (x) (cond ((atom x) (eq x nil)) (t nil)))

:def not (lambda (x) (cond (x nil) (t t)))

; --- 連ねる
:def append (label ap (lambda (xs ys)
  (cond ((null xs) ys)
        (t (cons (car xs) (ap (cdr xs) ys))))))

; --- 逆さにする
:def reverse (label rev (lambda (xs)
  (cond ((null xs) nil)
        (t (append (rev (cdr xs)) (cons (car xs) nil))))))

; --- その語が居るか
:def member (label mem (lambda (x xs)
  (cond ((null xs) nil)
        ((eq x (car xs)) t)
        (t (mem x (cdr xs))))))

; --- ひとつずつ、渡された関数にくぐらせる（関数を受けとる関数）
:def mapcar (label mc (lambda (f xs)
  (cond ((null xs) nil)
        (t (cons (f (car xs)) (mc f (cdr xs)))))))

; --- 語と語のあいだに、ひとつの語を挟む
:def 挟む (label f (lambda (w xs)
  (cond ((null xs) nil)
        ((null (cdr xs)) xs)
        (t (cons (car xs) (cons w (f w (cdr xs))))))))

; --- ある語を、別の語に置きかえる（深いところまで）
:def 置く (label sub (lambda (新 旧 x)
  (cond ((atom x) (cond ((eq x 旧) 新) (t x)))
        (t (mapcar (lambda (e) (sub 新 旧 e)) x)))))

; --- 二重にする
:def 重ねる (lambda (x) (cons x (cons x nil)))


; ------------------------------------------------------------------ 試してみる
(append '(雪 が) '(降る))                      ; (雪 が 降る)
(reverse '(海 へ 続く 道))                     ; (道 続く へ 海)
(member '夜 '(朝 昼 夜))                       ; t
(mapcar 重ねる '(遠く 近く))                   ; ((遠く 遠く) (近く 近く))
(mapcar car '((白い 鳥) (黒い 水)))            ; (白い 黒い)
(挟む 'と '(雪 風 夜))                         ; (雪 と 風 と 夜)
(置く '雨 '雪 '(雪 が (雪 の 上に) 降る))       ; (雨 が (雨 の 上に) 降る)

; 名前のない関数を、その場でつくって、その場で使う
((lambda (x) (append x (reverse x))) '(行き))  ; (行き 行き)
