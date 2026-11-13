import cv2

cap = cv2.VideoCapture(1,cv2.CAP_DSHOW)
haar = cv2.CascadeClassifier('prueba-alto1.xml')
font = cv2.FONT_HERSHEY_SIMPLEX

while True:
    
    ret,frame = cap.read()
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    prueba = haar.detectMultiScale(gray,1.3,3,2)
    
    for (x,y,w,h) in prueba:
        pt1=(x,y)
        pt2=(x+w,y+h)
        
        cv2.rectangle(frame, (x,y),(x+w,y+h),(255,0,0),2)
        cv2.rectangle(frame,(x,y),(x+100,y+40),(255, 0, 0),-1)
        cv2.putText(frame,'Trunks',(x+10,y+30),font, 0.7,(255,255,255),2)
        
    cv2.imshow('VIdeo',frame) 
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
    
cap.release()
cv2.destroyAllWindows()
