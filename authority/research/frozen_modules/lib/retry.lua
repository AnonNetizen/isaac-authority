retry_count=(retry_count or 0)+1;if retry_count==1 then error('retry-once')end;return {count=retry_count}
