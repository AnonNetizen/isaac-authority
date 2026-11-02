settings = __config()
cached = settings.amount
for i = 1, 12 do cached = cached + 1 end
cached_text = 'amount=' .. cached
return settings.amount, cached, cached_text
