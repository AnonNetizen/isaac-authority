local mod=RegisterMod('Single Evaluation Regression',1)
local constants={
 'constant-001','constant-002','constant-003','constant-004','constant-005','constant-006','constant-007','constant-008',
 'constant-009','constant-010','constant-011','constant-012','constant-013','constant-014','constant-015','constant-016',
 'constant-017','constant-018','constant-019','constant-020','constant-021','constant-022','constant-023','constant-024',
 'constant-025','constant-026','constant-027','constant-028','constant-029','constant-030','constant-031','constant-032',
 'constant-033','constant-034','constant-035','constant-036','constant-037','constant-038','constant-039','constant-040',
 'constant-041','constant-042','constant-043','constant-044','constant-045','constant-046','constant-047','constant-048',
 'constant-049','constant-050','constant-051','constant-052','constant-053','constant-054','constant-055','constant-056',
 'constant-057','constant-058','constant-059','constant-060','constant-061','constant-062','constant-063','constant-064',
 'constant-065','constant-066','constant-067','constant-068','constant-069','constant-070','constant-071','constant-072',
 'constant-073','constant-074','constant-075','constant-076','constant-077','constant-078','constant-079','constant-080'
}
local function missing(a,b,c,d,e)
 assert(a==7 and b==nil and c==nil and d==nil and e==nil)
 local f,g,h,i,j,k,l,m
 assert(f==nil and g==nil and h==nil and i==nil and j==nil and k==nil and l==nil and m==nil)
 return select('#',a,b,c,d,e,f,g,h,i,j,k,l,m)
end
for i=1,30 do assert(missing(7)==13);collectgarbage('collect') end
mod:AddCallback(2,function()
 assert(missing(7)==13)
 Isaac.RenderText(#constants..'|'..constants[1]..'|'..constants[80],0,0)
end)
