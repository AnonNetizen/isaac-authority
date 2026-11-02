settings.x = 193
other_writer(193)
for i = 1, 8 do settings['extra' .. i] = i end
return settings.amount, settings.x, reader(), cached, reader_alias()
