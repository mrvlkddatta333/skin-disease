from flask import Flask, render_template, request, flash, jsonify,get_flashed_messages,Response,session,redirect,url_for
import cv2, os
from ultralytics import YOLO
import pandas as pd
import mysql.connector
from flask_session import Session
from key import secret_key,salt,salt2
from itsdangerous import URLSafeTimedSerializer
from stoken import token
from cmail import sendmail
import mysql.connector.pooling

app = Flask(__name__)
app.secret_key = b'filesystem'
app.config['SESSION_TYPE']='filesystem'

# db=os.environ['RDS_DB_NAME']
# user=os.environ['RDS_USERNAME']
# password=os.environ['RDS_PASSWORD']
# host=os.environ['RDS_HOSTNAME']
# port=os.environ['RDS_PORT']

# conn=mysql.connector.pooling.MySQLConnectionPool(host=host,user=user,password=password,db=db,port=port,pool_name='DED',pool_size=3,pool_reset_session=True)

conn=mysql.connector.pooling.MySQLConnectionPool(host='localhost',user='root',password="admin",db='skin',pool_name='DED',pool_size=3, pool_reset_session=True)

try:
    mydb=conn.get_connection()
    cursor = mydb.cursor(buffered=True)
    cursor.execute('CREATE TABLE IF NOT EXISTS users (uid INT PRIMARY KEY auto_increment, username VARCHAR(50), password VARCHAR(15), email VARCHAR(60))')

except Exception as e:
    print(e)
finally:
    if mydb.is_connected():
        mydb.close()

# Load the pre-trained YOLO model
model = YOLO('best.pt')

# Read the COCO class list from a file
with open("coco.txt", "r") as my_file:
    class_list = my_file.read().split("\n")

@app.route('/login',methods=['GET','POST'])
def login():
    if session.get('username'):
        return redirect(url_for('index'))
    if request.method=='POST':
        print(request.form)
        name=request.form['name']
        password=request.form['password']
        try:
            mydb=conn.get_connection()
            cursor=mydb.cursor(buffered=True)
        except Exception as e:
            print(e)
        else:
            cursor.execute('SELECT count(*) from users where username=%s and password=%s',[name,password])
            count=cursor.fetchone()[0]
            cursor.close()
            if count==1:
                session['username']=name
                return redirect(url_for('index'))
            else:
                flash('Invalid username or password')
                return render_template('login.html')
        finally:
            if mydb.is_connected():
                mydb.close()
    return render_template('login.html')

@app.route('/registration',methods=['GET','POST'])
def registration():
    if request.method=='POST':
        username=request.form['username']
        password=request.form['password']
        email=request.form['email']
        try:
            mydb=conn.get_connection()
            cursor=mydb.cursor(buffered=True)
        except Exception as e:
            print(e)
        else:
            cursor.execute('SELECT COUNT(*) FROM users WHERE username = %s', [username])
            count=cursor.fetchone()[0]
            cursor.execute('select count(*) from users where email=%s',[email])
            count1=cursor.fetchone()[0]
            cursor.close()
            if count==1:
                flash('username already in use')
                return render_template('registration.html')
            elif count1==1:
                flash('Email already in use')
                return render_template('registration.html')
            data={'username':username,'password':password,'email':email}
            subject='Email Confirmation'
            body=f"Thanks for signing up\n\nfollow this link for further steps-{url_for('confirm',token=token(data,salt),_external=True)}"
            sendmail(to=email,subject=subject,body=body)
            flash('Confirmation link sent to mail')
            return redirect(url_for('login'))
        finally:
            if mydb.is_connected():
                mydb.close()
    return render_template('registration.html')

@app.route('/confirm/<token>')
def confirm(token):
    try:
        serializer=URLSafeTimedSerializer(secret_key)
        data=serializer.loads(token,salt=salt,max_age=180)
    except Exception as e:
        #print(e)
        return 'Link Expired register again'
    else:
        try:
            mydb=conn.get_connection()
            cursor=mydb.cursor(buffered=True)
        except Exception as e:
            print(e)
        else:
            username=data['username']
            cursor.execute('select count(*) from users where username=%s',[username])
            count=cursor.fetchone()[0]
            if count==1:
                cursor.close()
                flash('You are already registerterd!')
                return redirect(url_for('login'))
            else:
                cursor.execute('insert into users(username,password,email) values(%s,%s,%s)',(data['username'], data['password'], data['email']))
                mydb.commit()
                cursor.close()
                flash('Details registered!')
                return redirect(url_for('login'))
        finally:
            if mydb.is_connected():
                mydb.close()


@app.route('/forget',methods=['GET','POST'])
def forgot():
    if request.method=='POST':
        email=request.form['email']
        try:
            mydb=conn.get_connection()
            cursor=mydb.cursor(buffered=True)
        except Exception as e:
            print(e)
        else:
            cursor.execute('select count(*) from users where email=%s',[email])
            count=cursor.fetchone()[0]
            cursor.close()
            if count==1:
                cursor=mydb.cursor(buffered=True)
                cursor.execute('SELECT email from users where email=%s',[email])
                status=cursor.fetchone()[0]
                cursor.close()
                subject='Forget Password'
                confirm_link=url_for('reset',token=token(email,salt=salt2),_external=True)
                body=f"Use this link to reset your password-\n\n{confirm_link}"
                sendmail(to=email,body=body,subject=subject)
                flash('Reset link sent check your email')
                return redirect(url_for('login'))
            else:
                flash('Invalid email id')
                return render_template('forgot.html')
        finally:
            if mydb.is_connected():
                mydb.close()
    return render_template('forgot.html')


@app.route('/reset/<token>',methods=['GET','POST'])
def reset(token):
    try:
        serializer=URLSafeTimedSerializer(secret_key)
        email=serializer.loads(token,salt=salt2,max_age=180)
    except:
        abort(404,'Link Expired')
    else:
        if request.method=='POST':
            newpassword=request.form['npassword']
            confirmpassword=request.form['cpassword']
            if newpassword==confirmpassword:
                try:
                    mydb=conn.get_connection()
                    cursor=mydb.cursor(buffered=True)
                except Exception as e:
                    print(e)
                else:
                    cursor.execute('update users set password=%s where email=%s',[newpassword,email])
                    mydb.commit()
                    flash('Reset Successful')
                    return redirect(url_for('login'))
                finally:
                    if mydb.is_connected():
                        mydb.close()
            else:
                flash('Passwords mismatched')
                return render_template('newpassword.html')
        return render_template('newpassword.html')

@app.route('/logout')
def logout():
    if session.get('username'):
        session.pop('username')
        flash('Successfully logged out')
        return redirect(url_for('login'))
    else:
        return redirect(url_for('login'))


@app.route('/', methods=['GET', 'POST'])
def index():
    if session.get('username'):
        if request.method == 'POST':
            file = request.files['image']
            filename = file.filename
            file_path = f'static/images/{filename}'
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            file.save(file_path)
            flash('File Uploaded Successfully.', 'success')

            # Get flashed messages
            flash_messages = get_flashed_messages(with_categories=True)
            flash_messages = [{'category': msg[0], 'message': msg[1]} for msg in flash_messages]
            return jsonify({'file_path': file_path, 'filename': filename, 'flash_messages': flash_messages})
        return render_template('index.html')
    else:
        return redirect(url_for('login'))

@app.route('/detect_disease/<path:file_path>/<filename>', methods=['GET', 'POST'])
def detect_disease(file_path, filename):
    if session.get('username'):
        frame = cv2.imread(file_path)
        frame = cv2.resize(frame, (640, 500))

        results = model.predict(frame)
        detections = results[0].boxes.data
        if len(detections) == 0:
            flash('No disease detected. Please re-upload a proper image.', 'warning')
            # Get flashed messages
            flash_messages = get_flashed_messages(with_categories=True)
            flash_messages = [{'category': msg[0], 'message': msg[1]} for msg in flash_messages]
            return jsonify({'filename': filename, 'flash_messages': flash_messages})
        px = pd.DataFrame(detections).astype("float")

        diseases = set()
        for index, row in px.iterrows():
            x1, y1, x2, y2, _, d = map(int, row)
            if d < len(class_list):
                c = class_list[d]
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, str(c), (x1, y1), cv2.FONT_HERSHEY_COMPLEX, 0.5, (255, 0, 0), 1)
                diseases.add(c)
        if not diseases:
            flash('No diseases detected. Please re-upload a proper image.', 'warning')
        else:
            flash('Disease Detected Successfully.', 'success')
        output_path = f'static/detections/{filename}'
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        cv2.imwrite(output_path, frame)
        flash('Disease Detected Successfully.', 'success')
        # Get flashed messages
        flash_messages = get_flashed_messages(with_categories=True)
        flash_messages = [{'category': msg[0], 'message': msg[1]} for msg in flash_messages]
        return jsonify({'output_path': output_path, 'diseases': list(diseases), 'filename': filename, 'flash_messages': flash_messages})
    else:
        return redirect(url_for('login'))

@app.route('/get_medicines/<diseases>/<filename>', methods=['GET', 'POST'])
def get_medicines(diseases, filename):
    if session.get('username'):
        medicines = {
            "Acne": "Isotretinoin",
            "Chickenpox": "Acyclovir",
            "Monkeypox": "Tecovirimat",
            "Pimple": "Macrolide",
            "Eczema": "Corticosteroids",
            "Psoriasis": "Methotrexate",
            "Ringworm": "Clotrimazole",
            "basal cell carcinoma": "Erivedge",
            "melanoma": "Vemurafenib",
            "tinea-versicolor": "Terbinafine",
            "vitiligo": "Ruxolitinib",
            "warts": "Salicylic acid"
        }

        disease_list = diseases.split(',')
        medicine_dict = {disease: medicines.get(disease) for disease in disease_list}
        flash('Medicine Recommended Successfully!', 'success')
        # Get flashed messages
        flash_messages = get_flashed_messages(with_categories=True)
        flash_messages = [{'category': msg[0], 'message': msg[1]} for msg in flash_messages]
        return jsonify({'medicines': medicine_dict, 'filename': filename, 'flash_messages': flash_messages})
    else:
        return redirect(url_for('login'))


def gen_frames():
    cap = cv2.VideoCapture(0)
    while True:
        ret, frame = cap.read()
        frame = cv2.resize(frame, (1020, 500))
        results = model.predict(frame)
        detections = results[0].boxes.data
        px = pd.DataFrame(detections).astype("float")

        for index, row in px.iterrows():
            x1, y1, x2, y2, _, d = map(int, row)
            c = class_list[d]
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, str(c), (x1, y1), cv2.FONT_HERSHEY_COMPLEX, 0.5, (255, 0, 0), 1)

        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')


@app.route('/video_feed')
def video_feed():
    if session.get('username'):
        return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')
    else:
        return redirect(url_for('login'))



if __name__ == '__main__':
    app.run(    debug=True)
