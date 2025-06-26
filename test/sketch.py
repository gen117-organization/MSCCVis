l = []
for i in range(10):
    l.append({
        "a": i,
    })

print(l)

for item in l:
    item["a"] += 1

print(l)