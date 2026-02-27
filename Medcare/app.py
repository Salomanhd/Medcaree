import http.server
import socketserver
import json
import os
import urllib.request

PORT = 3000

# 2. Ma'lumotlar ombori (Oddiy ro'yxat ko'rinishida)
doctors = [
    {"id": 1, "name": "Dr. Alisher Karimov", "specialty": "Kardiolog", "exp": "15 yil"},
    {"id": 2, "name": "Dr. Nigora Yusupova", "specialty": "Pediatr", "exp": "8 yil"},
    {"id": 3, "name": "Dr. Jamshid To'rayev", "specialty": "Nevropatolog", "exp": "12 yil"}
]
medications = []
appointments = [] # Track appointments as objects: {"doc_id": id, "user_email": email}
users = [] # Track registered users

class MyHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            try:
                with open('index.html', 'rb') as f:
                    self.wfile.write(f.read())
            except FileNotFoundError:
                self.wfile.write(b"index.html topilmadi")
        elif self.path == '/api/doctors':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(doctors).encode())
        elif self.path == '/api/admin/stats':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            stats = {
                "total_doctors": len(doctors),
                "total_appointments": len(appointments),
                "total_meds": len(medications),
                "total_users": len(users)
            }
            self.wfile.write(json.dumps(stats).encode())
        elif self.path == '/api/auth/google/url':
            # Construct Google OAuth URL
            client_id = os.environ.get('GOOGLE_CLIENT_ID', 'YOUR_GOOGLE_CLIENT_ID')
            redirect_uri = "https://ais-dev-q7njnk5d3cq4t3atpomobb-132827535092.asia-east1.run.app/auth/google/callback"
            scope = "https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/userinfo.profile"
            auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code&scope={scope}&access_type=offline&prompt=consent"
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"url": auth_url}).encode())
        elif self.path.startswith('/auth/google/callback'):
            # Handle Google Callback
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            # In a real app, we'd exchange the code for tokens here
            self.wfile.write(b"""
                <html><body><script>
                    window.opener.postMessage({ type: 'OAUTH_AUTH_SUCCESS', user: { email: 'user@gmail.com', name: 'Google User' } }, '*');
                    window.close();
                </script></body></html>
            """)
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == '/api/check_symptoms':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data)
            symptoms = data.get('symptoms', '')

            api_key = os.environ.get('GEMINI_API_KEY')
            if not api_key:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(b"API key topilmadi")
                return

            # Gemini API call
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key={api_key}"
            
            prompt = f"""Siz tajribali tibbiy tahlilchisiz. Foydalanuvchi simptomlari: "{symptoms}".
            Javobni quyidagi formatda o'zbek tilida bering:
            1. 🩺 **Tahlil**: Simptomlarning qisqacha tibbiy tushuntirishi.
            2. 🌡️ **Ehtimoliy holatlar**: 2-3 ta asosiy variant.
            3. 👨‍⚕️ **Mutaxassis**: Qaysi shifokorga borish kerak.
            4. 🚨 **Xavf**: Qachon shoshilinch yordam kerak.
            5. ⚠️ **Eslatma**: Bu tashxis emas, maslahat xolos."""
            
            payload = {
                "contents": [{
                    "parts": [{"text": prompt}]
                }]
            }
            
            req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
            try:
                with urllib.request.urlopen(req) as response:
                    res_data = json.loads(response.read().decode())
                    if 'candidates' in res_data and len(res_data['candidates']) > 0:
                        analysis = res_data['candidates'][0]['content']['parts'][0]['text']
                        self.send_response(200)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({"analysis": analysis}).encode())
                    else:
                        error_msg = res_data.get('error', {}).get('message', 'Noma\'lum xatolik')
                        raise Exception(f"AI Error: {error_msg}")
            except urllib.error.HTTPError as e:
                error_body = e.read().decode()
                print(f"HTTP Error: {error_body}")
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"API xatosi: {e.code}"}).encode())
            except Exception as e:
                print(f"General Error: {str(e)}")
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        
        elif self.path == '/api/book_appointment':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data)
            
            appointments.append({
                "doc_id": data.get('doc_id'),
                "user_email": data.get('user_email')
            })
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())

        elif self.path == '/api/admin/add_doctor':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data)
            
            new_id = max([d['id'] for d in doctors]) + 1 if doctors else 1
            new_doctor = {
                "id": new_id,
                "name": data.get('name'),
                "specialty": data.get('specialty'),
                "exp": data.get('exp')
            }
            doctors.append(new_doctor)
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "doctor": new_doctor}).encode())

        elif self.path == '/api/admin/delete_doctor':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data)
            doc_id = data.get('id')
            
            global doctors, appointments
            doctors = [d for d in doctors if d['id'] != doc_id]
            # Also remove appointments for this doctor
            appointments = [a for a in appointments if a['doc_id'] != doc_id]
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())
        
        elif self.path == '/api/auth/register':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            user_data = json.loads(post_data)
            if user_data not in users:
                users.append(user_data)
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())

        elif self.path == '/api/send_email':
            # Mock email sending
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data)
            email = data.get('email')
            meds = data.get('meds', [])
            
            print(f"Email yuborilmoqda: {email}")
            print(f"Dorilar: {meds}")
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "message": "Email muvaffaqiyatli yuborildi (simulyatsiya)"}).encode())

with socketserver.TCPServer(("", PORT), MyHandler) as httpd:
    print(f"Serving at port {PORT}")
    httpd.serve_forever()
