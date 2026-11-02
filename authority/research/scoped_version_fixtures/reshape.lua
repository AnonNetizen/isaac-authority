for i = 1, 32 do observed['field' .. i] = i end
observed.keep = __tag(9, 'personal_option:restored')
writer(__tag(13, 'world:restored'))
return observed.keep, reader(), reader_alias()
