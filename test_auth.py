import requests
session = requests.Session()
login_data = {'username': 'admin', 'password': 'password123', 'next': '/admin/'}
response = session.get('http://localhost:8000/admin/login/')
csrftoken = response.cookies['csrftoken']
login_data['csrfmiddlewaretoken'] = csrftoken
res = session.post('http://localhost:8000/admin/login/', data=login_data, headers={'Referer': 'http://localhost:8000/admin/login/'})
print("Login status:", res.status_code)
pdf_res = session.get('http://localhost:8000/api/submissions/export-compliance-pdf/')
print("PDF Export status:", pdf_res.status_code)
print(pdf_res.text[:200])
