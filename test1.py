a=5
b=-9
if a==b:
	print("a=",a)
elif a>b:
     print("a>",b)
else:
     print("you are debt")


try:
    a=a+1
    a=a/1
except BufferError:
    print(a)
except:
    print("don't do that")
print("a can't division by 0")

