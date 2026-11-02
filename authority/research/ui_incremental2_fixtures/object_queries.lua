local t = {kept = __tag(5, 'field')}
__tag(t, 'container')
return t.kept, t.missing, rawget(t, 'missing'), #t, rawlen(t), type(t)
