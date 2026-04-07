import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from io import BytesIO
import re
import qrcode
from PIL import Image
import os
import json
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import plotly.express as px
import plotly.graph_objects as go
import cv2
import numpy as np
from pyzbar.pyzbar import decode
import time
import io
import zipfile
from supabase import create_client, Client
from dateutil import tz

# ==========================================
# CONFIGURACIÓN DE ZONA HORARIA MÉXICO
# ==========================================
MEXICO_TZ = tz.gettz('America/Mexico_City')

def get_mexico_time():
    return datetime.now(MEXICO_TZ)

def get_mexico_date():
    return get_mexico_time().date()

def get_mexico_datetime():
    return get_mexico_time()

def get_mexico_week():
    return get_mexico_date().isocalendar()[1]

def get_mexico_day_spanish():
    dias = {'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miércoles', 
            'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'Sábado', 'Sunday': 'Domingo'}
    return dias[get_mexico_date().strftime('%A')]

# ==========================================
# CONEXIÓN A SUPABASE
# ==========================================
@st.cache_resource
def init_supabase() -> Client:
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except:
        try:
            url = os.getenv("SUPABASE_URL", "https://tu-proyecto.supabase.co")
            key = os.getenv("SUPABASE_KEY", "tu-anon-key")
            return create_client(url, key)
        except Exception as e:
            st.error(f"❌ Error de conexión: {str(e)}")
            return None

supabase = init_supabase()

# ==========================================
# CONFIGURACIÓN INICIAL
# ==========================================
st.set_page_config(
    page_title="Sistema Integral de Gestión Agrícola",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .stButton > button { width: 100%; border-radius: 10px; padding: 12px; font-weight: bold; margin-bottom: 8px; }
    .stButton > button:hover { transform: translateX(5px); box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
    .sidebar-title { text-align: center; padding: 20px 0; border-bottom: 2px solid #e0e0e0; margin-bottom: 20px; }
    .sidebar-title h2 { color: #2c3e50; margin: 0; }
    .user-info { padding: 10px; background: #f0f2f6; border-radius: 10px; margin-bottom: 20px; text-align: center; }
    .kpi-card { background: linear-gradient(135deg, #1e3c2c 0%, #2a6b3c 100%); border-radius: 15px; padding: 15px; color: white; text-align: center; margin-bottom: 15px; }
    .kpi-card * { color: white !important; }
    .kpi-value { font-size: 28px; font-weight: bold; color: white !important; }
    .kpi-label { font-size: 12px; opacity: 0.9; margin-top: 5px; color: white !important; }
    .date-card { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 12px; padding: 12px; text-align: center; color: white !important; }
    .date-card * { color: white !important; }
    .time-card { background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); border-radius: 12px; padding: 12px; text-align: center; color: white !important; }
    .time-card * { color: white !important; }
    .week-card { background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%); border-radius: 12px; padding: 12px; text-align: center; color: white !important; }
    .week-card * { color: white !important; }
    .section-title { font-size: 24px; font-weight: bold; color: #1e3c2c; margin: 20px 0 15px 0; border-left: 4px solid #2a6b3c; padding-left: 15px; }
    .login-container { max-width: 400px; margin: 100px auto; padding: 30px; background: white; border-radius: 15px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }
    div[data-testid="stMetricValue"] { color: white !important; }
    div[data-testid="stMetricLabel"] { color: white !important; }
    </style>
""", unsafe_allow_html=True)

REPORTE_TURNOS = ["Reporte 10:00am", "Reporte 12:00pm", "Reporte 02:00pm", "Reporte 03:00pm", 
                  "Reporte 04:00pm", "Reporte 05:00pm", "Reporte 06:00pm", "Reporte 07:00pm", "Reporte 08:00pm"]

# ==========================================
# FUNCIONES DE AUTENTICACIÓN
# ==========================================
def obtener_permisos_usuario(user_id):
    try:
        result = supabase.table('perfiles_usuario').select('permisos, rol, invernaderos_asignados').eq('id', user_id).execute()
        if result.data:
            return result.data[0].get('permisos', {}), result.data[0].get('rol'), result.data[0].get('invernaderos_asignados', [])
    except:
        pass
    return {}, 'supervisor', []

def get_configuracion_sistema(clave):
    try:
        result = supabase.table('configuracion_sistema').select('valor').eq('clave', clave).execute()
        if result.data:
            return result.data[0]['valor'] == 'true'
    except:
        pass
    return True

def login_user(email, password):
    try:
        response = supabase.auth.sign_in_with_password({"email": email, "password": password})
        if response.user:
            perfil = supabase.table('perfiles_usuario').select('*').eq('id', response.user.id).execute()
            rol = 'supervisor'
            nombre = email.split('@')[0]
            permisos = {}
            invernaderos_asignados = []
            if perfil.data and len(perfil.data) > 0:
                rol = perfil.data[0].get('rol', 'supervisor')
                nombre = perfil.data[0].get('nombre', nombre)
                permisos = perfil.data[0].get('permisos', {})
                invernaderos_asignados = perfil.data[0].get('invernaderos_asignados', [])
            return {'success': True, 'user_id': response.user.id, 'email': email, 'rol': rol, 
                    'nombre': nombre, 'permisos': permisos, 'invernaderos_asignados': invernaderos_asignados}
    except Exception as e:
        return {'success': False, 'error': str(e)}
    return {'success': False, 'error': 'Error de autenticación'}

def register_user(email, password, nombre, rol='supervisor', permisos=None, invernaderos_asignados=None):
    try:
        response = supabase.auth.sign_up({"email": email, "password": password, "options": {"data": {"nombre": nombre}}})
        if response.user:
            permisos_default = {
                "gestion_personal": False, "registro_cosecha": True, "registro_asistencia": True,
                "avance_cosecha": True, "traslado_camara_fria": True, "gestion_merma": True,
                "proyecciones": True, "generar_qr": False, "reportes": True, "catalogos": False,
                "gestion_invernaderos": False, "dashboard": True, "pesaje_cajas": True,
                "cajas_mesa": True, "cierre_dia": False, "gestion_usuarios": False, "auditoria_diaria": True
            }
            if permisos:
                permisos_default.update(permisos)
            supabase.table('perfiles_usuario').insert({
                'id': response.user.id, 'email': email, 'nombre': nombre, 'rol': rol,
                'permisos': permisos_default, 'invernaderos_asignados': invernaderos_asignados or []
            }).execute()
            return {'success': True, 'message': 'Usuario registrado exitosamente'}
    except Exception as e:
        return {'success': False, 'error': str(e)}
    return {'success': False, 'error': 'Error al registrar usuario'}

def logout_user():
    try:
        supabase.auth.sign_out()
    except:
        pass
    for key in ['user_id', 'user_email', 'user_rol', 'user_nombre', 'authenticated', 'user_permisos', 'user_invernaderos']:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()

def show_login_page():
    st.markdown('<div style="text-align: center; padding: 40px 0;"><h1>🌾 Sistema Integral de Gestión Agrícola</h1><p>Acceda con sus credenciales</p></div>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.container():
            st.markdown('<div class="login-container">', unsafe_allow_html=True)
            tab1, tab2 = st.tabs(["🔐 Iniciar Sesión", "📝 Registrarse"])
            with tab1:
                email = st.text_input("Email", key="login_email")
                password = st.text_input("Contraseña", type="password", key="login_password")
                if st.button("Ingresar", type="primary", use_container_width=True):
                    if email and password:
                        result = login_user(email, password)
                        if result['success']:
                            st.session_state.authenticated = True
                            st.session_state.user_id = result['user_id']
                            st.session_state.user_email = result['email']
                            st.session_state.user_rol = result['rol']
                            st.session_state.user_nombre = result['nombre']
                            st.session_state.user_permisos = result.get('permisos', {})
                            st.session_state.user_invernaderos = result.get('invernaderos_asignados', [])
                            st.success(f"✅ Bienvenido {result['nombre']}")
                            st.rerun()
                        else:
                            st.error(result['error'])
                    else:
                        st.error("Ingrese email y contraseña")
            with tab2:
                reg_email = st.text_input("Email", key="reg_email")
                reg_password = st.text_input("Contraseña", type="password", key="reg_password")
                reg_confirm = st.text_input("Confirmar Contraseña", type="password", key="reg_confirm")
                reg_nombre = st.text_input("Nombre completo", key="reg_nombre")
                reg_rol = st.selectbox("Rol", ["supervisor", "admin"], key="reg_rol")
                if st.button("Registrarse", type="primary", use_container_width=True):
                    if reg_email and reg_password and reg_nombre:
                        if reg_password != reg_confirm:
                            st.error("Las contraseñas no coinciden")
                        elif len(reg_password) < 6:
                            st.error("La contraseña debe tener al menos 6 caracteres")
                        else:
                            result = register_user(reg_email, reg_password, reg_nombre, reg_rol)
                            if result['success']:
                                st.success(result['message'])
                                st.info("Ahora puedes iniciar sesión")
                            else:
                                st.error(result['error'])
                    else:
                        st.error("Complete todos los campos")
            st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# FUNCIONES DE UTILIDAD
# ==========================================
def invalidar_cache():
    st.cache_data.clear()

def export_to_excel(df, sheet_name="Datos"):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    output.seek(0)
    return output

def validar_email(email):
    if not email or pd.isna(email):
        return True
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(pattern, email) is not None

def validar_telefono(telefono):
    if not telefono or pd.isna(telefono):
        return True
    return telefono.isdigit() and len(telefono) == 10

# ==========================================
# FUNCIONES PARA CATÁLOGOS
# ==========================================
def get_departamentos():
    try:
        result = supabase.table('departamentos').select('id, nombre').order('nombre').execute()
        return [(row['id'], row['nombre']) for row in result.data]
    except:
        return []

def get_subdepartamentos():
    try:
        result = supabase.table('subdepartamentos').select('id, nombre').order('nombre').execute()
        return [(row['id'], row['nombre']) for row in result.data]
    except:
        return []

def get_puestos():
    try:
        result = supabase.table('puestos').select('id, nombre').order('nombre').execute()
        return [(row['id'], row['nombre']) for row in result.data]
    except:
        return []

def get_departamentos_nombres():
    return [nombre for _, nombre in get_departamentos()]

def get_subdepartamentos_nombres():
    return [nombre for _, nombre in get_subdepartamentos()]

def get_puestos_nombres():
    return [nombre for _, nombre in get_puestos()]

def get_all_invernaderos():
    try:
        result = supabase.table('invernaderos').select('id, nombre, ubicacion, lineas_totales').eq('activo', True).order('nombre').execute()
        return [(row['id'], row['nombre'], row['ubicacion'], row.get('lineas_totales', 40)) for row in result.data]
    except:
        return []

def get_invernaderos():
    return get_all_invernaderos()

def get_invernaderos_usuario():
    if st.session_state.get('user_rol') == 'admin':
        return get_all_invernaderos()
    else:
        invernaderos_asignados = st.session_state.get('user_invernaderos', [])
        if not invernaderos_asignados:
            return []
        result = supabase.table('invernaderos').select('id, nombre, ubicacion, lineas_totales').in_('id', invernaderos_asignados).eq('activo', True).execute()
        return [(row['id'], row['nombre'], row['ubicacion'], row.get('lineas_totales', 40)) for row in result.data] if result.data else []

def add_catalog_item(tabla, nombre):
    try:
        supabase.table(tabla).insert({'nombre': nombre.lower().strip()}).execute()
        invalidar_cache()
        return True, "✅ Item agregado correctamente"
    except Exception as e:
        if 'duplicate key' in str(e).lower():
            return False, "❌ Este nombre ya existe"
        return False, f"❌ Error: {str(e)}"

def update_catalog_item(tabla, item_id, nuevo_nombre):
    try:
        supabase.table(tabla).update({'nombre': nuevo_nombre.lower().strip()}).eq('id', item_id).execute()
        invalidar_cache()
        return True, "✅ Item actualizado correctamente"
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

def delete_catalog_item(tabla, item_id):
    try:
        if tabla == "departamentos":
            check = supabase.table('trabajadores').select('id', count='exact').eq('departamento_id', item_id).execute()
        elif tabla == "subdepartamentos":
            check = supabase.table('trabajadores').select('id', count='exact').eq('subdepartamento_id', item_id).execute()
        else:
            check = supabase.table('trabajadores').select('id', count='exact').eq('puesto_id', item_id).execute()
        if check.count and check.count > 0:
            return False, f"❌ No se puede eliminar: {check.count} trabajadores lo están usando"
        supabase.table(tabla).delete().eq('id', item_id).execute()
        invalidar_cache()
        return True, "✅ Item eliminado correctamente"
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

# ==========================================
# FUNCIONES DE TRABAJADORES
# ==========================================
def get_id_by_nombre(tabla, nombre):
    try:
        result = supabase.table(tabla).select('id').eq('nombre', nombre).execute()
        if result.data:
            return result.data[0]['id']
        return None
    except:
        return None

def get_all_workers():
    try:
        result = supabase.table('trabajadores').select("""
            id, nombre, apellido_paterno, apellido_materno, correo, telefono, estatus, fecha_alta, fecha_baja, tipo_nomina,
            departamentos:departamento_id (nombre), subdepartamentos:subdepartamento_id (nombre), puestos:puesto_id (nombre)
        """).eq('estatus', 'activo').order('apellido_paterno').execute()
        data = []
        for row in result.data:
            data.append({
                'id': row['id'], 'nombre': row['nombre'], 'apellido_paterno': row['apellido_paterno'],
                'apellido_materno': row['apellido_materno'] or '', 'correo': row['correo'] or '', 'telefono': row['telefono'] or '',
                'estatus': row['estatus'], 'fecha_alta': row['fecha_alta'], 'fecha_baja': row['fecha_baja'],
                'departamento': row['departamentos']['nombre'] if row['departamentos'] else 'Sin asignar',
                'subdepartamento': row['subdepartamentos']['nombre'] if row['subdepartamentos'] else 'Sin asignar',
                'puesto': row['puestos']['nombre'] if row['puestos'] else 'Sin asignar', 'tipo_nomina': row['tipo_nomina']
            })
        return pd.DataFrame(data)
    except Exception as e:
        return pd.DataFrame()

def get_worker_by_id(worker_id):
    try:
        result = supabase.table('trabajadores').select("""
            *, departamentos:departamento_id (nombre), subdepartamentos:subdepartamento_id (nombre), puestos:puesto_id (nombre)
        """).eq('id', worker_id).execute()
        if result.data:
            row = result.data[0]
            return {
                'id': row['id'], 'nombre': row['nombre'], 'apellido_paterno': row['apellido_paterno'],
                'apellido_materno': row['apellido_materno'] or '', 'correo': row['correo'], 'telefono': row['telefono'],
                'estatus': row['estatus'], 'fecha_alta': row['fecha_alta'], 'fecha_baja': row['fecha_baja'],
                'departamento_id': row['departamento_id'], 'subdepartamento_id': row['subdepartamento_id'],
                'puesto_id': row['puesto_id'], 'tipo_nomina': row['tipo_nomina'],
                'departamento_nombre': row['departamentos']['nombre'] if row['departamentos'] else '',
                'subdepartamento_nombre': row['subdepartamentos']['nombre'] if row['subdepartamentos'] else '',
                'puesto_nombre': row['puestos']['nombre'] if row['puestos'] else ''
            }
        return None
    except:
        return None

def add_worker(data):
    try:
        depto_id = get_id_by_nombre("departamentos", data['departamento'])
        sub_id = get_id_by_nombre("subdepartamentos", data['subdepartamento'])
        puesto_id = get_id_by_nombre("puestos", data['puesto'])
        supabase.table('trabajadores').insert({
            'apellido_paterno': data['ap'], 'apellido_materno': data['am'], 'nombre': data['nom'],
            'correo': data['cor'], 'telefono': data['tel'], 'fecha_alta': data['fa'], 'estatus': 'activo',
            'departamento_id': depto_id, 'subdepartamento_id': sub_id, 'tipo_nomina': data['tn'], 'puesto_id': puesto_id
        }).execute()
        invalidar_cache()
        return True, "✅ Trabajador guardado correctamente"
    except Exception as e:
        return False, f"❌ Error al guardar: {str(e)}"

def update_worker(worker_id, data):
    try:
        depto_id = get_id_by_nombre("departamentos", data['departamento'])
        sub_id = get_id_by_nombre("subdepartamentos", data['subdepartamento'])
        puesto_id = get_id_by_nombre("puestos", data['puesto'])
        supabase.table('trabajadores').update({
            'apellido_paterno': data['apellido_paterno'], 'apellido_materno': data['apellido_materno'],
            'nombre': data['nombre'], 'correo': data['correo'], 'telefono': data['telefono'],
            'departamento_id': depto_id, 'subdepartamento_id': sub_id, 'tipo_nomina': data['tipo_nomina'],
            'puesto_id': puesto_id, 'estatus': data['estatus'], 'updated_at': get_mexico_datetime().isoformat()
        }).eq('id', worker_id).execute()
        invalidar_cache()
        return True, "✅ Cambios guardados correctamente"
    except Exception as e:
        return False, f"❌ Error al actualizar: {str(e)}"

def dar_baja(worker_id, fecha_baja):
    try:
        supabase.table('trabajadores').update({'estatus': 'baja', 'fecha_baja': fecha_baja, 'updated_at': get_mexico_datetime().isoformat()}).eq('id', worker_id).execute()
        invalidar_cache()
        return True, f"✅ Trabajador dado de baja correctamente"
    except Exception as e:
        return False, f"❌ Error al dar de baja: {str(e)}"

def reactivar_trabajador(worker_id):
    try:
        supabase.table('trabajadores').update({'estatus': 'activo', 'fecha_baja': None, 'updated_at': get_mexico_datetime().isoformat()}).eq('id', worker_id).execute()
        invalidar_cache()
        return True, f"✅ Trabajador reactivado correctamente"
    except Exception as e:
        return False, f"❌ Error al reactivar: {str(e)}"

def search_workers(search_term, estatus_filter="todos"):
    try:
        query = supabase.table('trabajadores').select("""
            id, nombre, apellido_paterno, apellido_materno, correo, telefono, estatus, fecha_alta, fecha_baja, tipo_nomina,
            departamentos:departamento_id (nombre), subdepartamentos:subdepartamento_id (nombre), puestos:puesto_id (nombre)
        """)
        if search_term:
            query = query.or_(f"nombre.ilike.%{search_term}%,apellido_paterno.ilike.%{search_term}%,apellido_materno.ilike.%{search_term}%")
        if estatus_filter != "todos":
            query = query.eq('estatus', estatus_filter)
        result = query.order('apellido_paterno').execute()
        data = []
        for row in result.data:
            data.append({
                'id': row['id'], 'nombre': row['nombre'], 'apellido_paterno': row['apellido_paterno'],
                'apellido_materno': row['apellido_materno'] or '', 'correo': row['correo'] or '', 'telefono': row['telefono'] or '',
                'estatus': row['estatus'], 'fecha_alta': row['fecha_alta'], 'fecha_baja': row['fecha_baja'],
                'departamento': row['departamentos']['nombre'] if row['departamentos'] else 'Sin asignar',
                'subdepartamento': row['subdepartamentos']['nombre'] if row['subdepartamentos'] else 'Sin asignar',
                'puesto': row['puestos']['nombre'] if row['puestos'] else 'Sin asignar', 'tipo_nomina': row['tipo_nomina']
            })
        return pd.DataFrame(data)
    except Exception as e:
        return pd.DataFrame()

def get_recolectores():
    try:
        result = supabase.table('trabajadores').select('id, nombre, apellido_paterno').eq('estatus', 'activo').execute()
        return [(row['id'], f"{row['nombre']} {row['apellido_paterno']}") for row in result.data]
    except:
        return []

def get_pesadores():
    try:
        result = supabase.table('trabajadores').select('id, nombre, apellido_paterno, puestos:puesto_id (nombre)').eq('estatus', 'activo').execute()
        pesadores = []
        for row in result.data:
            puesto_nombre = row['puestos']['nombre'] if row['puestos'] else ''
            if 'pesador' in puesto_nombre.lower() or 'calidad' in puesto_nombre.lower():
                pesadores.append((row['id'], f"{row['nombre']} {row['apellido_paterno']}"))
        if not pesadores:
            pesadores = [(row['id'], f"{row['nombre']} {row['apellido_paterno']}") for row in result.data]
        return pesadores
    except:
        return []

# ==========================================
# FUNCIONES PARA INVERNADEROS
# ==========================================
def add_invernadero(nombre, ubicacion):
    try:
        supabase.table('invernaderos').insert({'nombre': nombre.strip().upper(), 'ubicacion': ubicacion, 'activo': True}).execute()
        invalidar_cache()
        return True, "✅ Invernadero agregado correctamente"
    except Exception as e:
        if 'duplicate key' in str(e).lower():
            return False, "❌ Este invernadero ya existe"
        return False, f"❌ Error: {str(e)}"

def update_invernadero(invernadero_id, nombre, ubicacion):
    try:
        supabase.table('invernaderos').update({'nombre': nombre.strip().upper(), 'ubicacion': ubicacion}).eq('id', invernadero_id).execute()
        invalidar_cache()
        return True, "✅ Invernadero actualizado correctamente"
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

def delete_invernadero(invernadero_id):
    try:
        check = supabase.table('asistencia').select('id', count='exact').eq('invernadero_id', invernadero_id).execute()
        if check.count and check.count > 0:
            supabase.table('invernaderos').update({'activo': False}).eq('id', invernadero_id).execute()
            invalidar_cache()
            return True, "✅ Invernadero desactivado correctamente"
        supabase.table('invernaderos').delete().eq('id', invernadero_id).execute()
        invalidar_cache()
        return True, "✅ Invernadero eliminado correctamente"
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

# ==========================================
# FUNCIONES DE AVANCE DE COSECHA
# ==========================================
def get_lineas_totales_por_invernadero(invernadero_id, invernadero_nombre):
    import re
    match = re.search(r'\d+', invernadero_nombre)
    if match:
        numero = int(match.group())
        if 1 <= numero <= 8:
            return 40
        elif 9 <= numero <= 11:
            return 36
    return 40

def get_ultimo_avance_dia(invernadero_id, fecha=None):
    if not fecha:
        fecha = get_mexico_date()
    try:
        result = supabase.table('avance_cosecha').select('lineas_cosechadas, porcentaje, hora, turno, es_acumulado')\
            .eq('invernadero_id', invernadero_id).eq('fecha', fecha.isoformat()).order('created_at', desc=True).limit(1).execute()
        if result.data:
            row = result.data[0]
            return {'lineas_cosechadas': row['lineas_cosechadas'], 'porcentaje': row['porcentaje'], 
                    'hora': row['hora'], 'turno': row['turno'], 'es_acumulado': row['es_acumulado']}
        return None
    except:
        return None

def get_avance_hoy_por_invernadero():
    fecha_hoy = get_mexico_date().isoformat()
    try:
        result = supabase.table('avance_cosecha').select("*, invernaderos:invernadero_id (nombre)").eq('fecha', fecha_hoy).execute()
        ultimos = {}
        for row in result.data:
            inv_id = row['invernadero_id']
            if inv_id not in ultimos or row['created_at'] > ultimos[inv_id]['created_at']:
                ultimos[inv_id] = row
        data = []
        for inv_id, row in ultimos.items():
            data.append({
                'id': row['id'], 'invernadero_id': inv_id, 'fecha': row['fecha'], 'hora': row['hora'], 'turno': row['turno'],
                'semana': row['semana'], 'lineas_cosechadas': row['lineas_cosechadas'], 'lineas_totales': row['lineas_totales'],
                'porcentaje': row['porcentaje'], 'supervisor': row['supervisor'], 'observaciones': row['observaciones'],
                'es_acumulado': row['es_acumulado'], 'invernadero_nombre': row['invernaderos']['nombre'] if row['invernaderos'] else 'Desconocido'
            })
        invernaderos = get_invernaderos()
        inv_con_datos = set([d['invernadero_id'] for d in data])
        for inv_id, inv_nombre, inv_ubic, _ in invernaderos:
            if inv_id not in inv_con_datos:
                lineas_totales = get_lineas_totales_por_invernadero(inv_id, inv_nombre)
                data.append({
                    'id': None, 'invernadero_id': inv_id, 'fecha': fecha_hoy, 'hora': None, 'turno': None,
                    'semana': get_mexico_week(), 'lineas_cosechadas': 0, 'lineas_totales': lineas_totales,
                    'porcentaje': 0.0, 'supervisor': None, 'observaciones': None, 'es_acumulado': 0, 
                    'invernadero_nombre': inv_nombre
                })
        return pd.DataFrame(data)
    except Exception as e:
        return pd.DataFrame()

def get_avance_historico_por_dia(fecha_inicio=None, fecha_fin=None, invernadero_id=None, turno=None):
    if not fecha_inicio:
        fecha_inicio = get_mexico_date() - timedelta(days=30)
    if not fecha_fin:
        fecha_fin = get_mexico_date()
    try:
        query = supabase.table('avance_cosecha').select("*, invernaderos:invernadero_id (nombre)").gte('fecha', fecha_inicio.isoformat()).lte('fecha', fecha_fin.isoformat())
        if invernadero_id:
            query = query.eq('invernadero_id', invernadero_id)
        if turno:
            query = query.eq('turno', turno)
        result = query.order('fecha', desc=True).order('created_at', desc=True).execute()
        ultimos = {}
        for row in result.data:
            key = f"{row['invernadero_id']}_{row['fecha']}"
            if key not in ultimos:
                ultimos[key] = row
        data = []
        for row in ultimos.values():
            data.append({
                'id': row['id'], 'invernadero_id': row['invernadero_id'], 'fecha': row['fecha'], 'hora': row['hora'],
                'turno': row['turno'], 'semana': row['semana'], 'lineas_cosechadas': row['lineas_cosechadas'],
                'lineas_totales': row['lineas_totales'], 'porcentaje': row['porcentaje'], 'supervisor': row['supervisor'],
                'observaciones': row['observaciones'], 'es_acumulado': row['es_acumulado'],
                'invernadero_nombre': row['invernaderos']['nombre'] if row['invernaderos'] else 'Desconocido'
            })
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

def registrar_avance_cosecha(invernadero_id, invernadero_nombre, lineas_cosechadas, supervisor, observaciones, turno=None):
    try:
        fecha_actual = get_mexico_date()
        hora_actual = get_mexico_time().strftime("%H:%M:%S")
        semana_actual = get_mexico_week()
        lineas_totales = get_lineas_totales_por_invernadero(invernadero_id, invernadero_nombre)
        
        check = supabase.table('avance_cosecha').select('id', count='exact').eq('invernadero_id', invernadero_id).eq('fecha', fecha_actual.isoformat()).execute()
        registros_hoy = check.count if check.count else 0
        
        if lineas_cosechadas > lineas_totales:
            return False, f"❌ Las líneas cosechadas ({lineas_cosechadas}) no pueden exceder el total ({lineas_totales})"
        
        if not turno:
            hora_int = int(hora_actual.split(':')[0])
            if 6 <= hora_int < 10:
                turno = "Reporte 10:00am"
            elif 10 <= hora_int < 12:
                turno = "Reporte 12:00pm"
            elif 12 <= hora_int < 14:
                turno = "Reporte 02:00pm"
            elif 14 <= hora_int < 15:
                turno = "Reporte 03:00pm"
            elif 15 <= hora_int < 16:
                turno = "Reporte 04:00pm"
            elif 16 <= hora_int < 17:
                turno = "Reporte 05:00pm"
            elif 17 <= hora_int < 18:
                turno = "Reporte 06:00pm"
            elif 18 <= hora_int < 19:
                turno = "Reporte 07:00pm"
            else:
                turno = "Reporte 08:00pm"
        
        porcentaje = (lineas_cosechadas / lineas_totales) * 100
        
        supabase.table('avance_cosecha').insert({
            'invernadero_id': invernadero_id, 'fecha': fecha_actual.isoformat(), 'hora': hora_actual,
            'turno': turno, 'semana': semana_actual, 'lineas_cosechadas': lineas_cosechadas,
            'lineas_totales': lineas_totales, 'porcentaje': porcentaje, 'supervisor': supervisor,
            'observaciones': observaciones, 'es_acumulado': False
        }).execute()
        
        invalidar_cache()
        
        if registros_hoy == 0:
            return True, f"✅ Primer avance del día registrado: {porcentaje:.1f}% completado (Turno: {turno})"
        else:
            return True, f"✅ Avance actualizado: {porcentaje:.1f}% completado (Turno: {turno})"
    except Exception as e:
        return False, f"❌ Error al registrar avance: {str(e)}"

# ==========================================
# FUNCIONES DE COSECHA Y TRASLADOS
# ==========================================
def guardar_cosecha(data):
    try:
        if data['presentacion'] == "12 oz":
            numero_cajas = data['cantidad_clams'] / 6
        else:
            numero_cajas = data['cantidad_clams'] / 12
        porcentaje_merma = (data.get('merma_kilos', 0) / data['cantidad_clams'] * 100) if data['cantidad_clams'] > 0 else 0
        supabase.table('cosechas').insert({
            'fecha': data['fecha'].isoformat() if isinstance(data['fecha'], date) else data['fecha'],
            'dia': data['dia'], 'semana': data['semana'], 'trabajador_id': data['trabajador_id'],
            'invernadero_id': data['invernadero_id'], 'tipo_cosecha': data['tipo_cosecha'],
            'calidad': data['calidad'], 'presentacion': data['presentacion'],
            'cantidad_clams': data['cantidad_clams'], 'numero_cajas': numero_cajas,
            'cajas_enviadas': 0, 'merma_kilos': data.get('merma_kilos', 0),
            'porcentaje_merma': porcentaje_merma, 'observaciones': data.get('observaciones', '')
        }).execute()
        invalidar_cache()
        return True, f"✅ Cosecha registrada correctamente - {numero_cajas:.2f} cajas - Merma: {data.get('merma_kilos', 0):.2f} kg ({porcentaje_merma:.1f}%)"
    except Exception as e:
        return False, f"❌ Error al guardar: {str(e)}"

def get_cosechas(fecha_inicio=None, fecha_fin=None, invernadero_id=None):
    try:
        query = supabase.table('cosechas').select("""
            *, trabajadores:trabajador_id (nombre, apellido_paterno), invernaderos:invernadero_id (nombre)
        """)
        if fecha_inicio:
            query = query.gte('fecha', fecha_inicio.isoformat() if isinstance(fecha_inicio, date) else fecha_inicio)
        if fecha_fin:
            query = query.lte('fecha', fecha_fin.isoformat() if isinstance(fecha_fin, date) else fecha_fin)
        if invernadero_id:
            query = query.eq('invernadero_id', invernadero_id)
        result = query.order('fecha', desc=True).order('id', desc=True).execute()
        data = []
        for row in result.data:
            trabajador_nombre = f"{row['trabajadores'].get('nombre', '')} {row['trabajadores'].get('apellido_paterno', '')}" if row['trabajadores'] else ""
            data.append({
                'id': row['id'], 'fecha': row['fecha'], 'dia': row['dia'], 'semana': row['semana'],
                'trabajador_id': row['trabajador_id'], 'trabajador_nombre': trabajador_nombre,
                'invernadero_id': row['invernadero_id'], 'invernadero_nombre': row['invernaderos']['nombre'] if row['invernaderos'] else 'Desconocido',
                'tipo_cosecha': row['tipo_cosecha'], 'calidad': row.get('calidad', ''), 'presentacion': row['presentacion'],
                'cantidad_clams': row['cantidad_clams'], 'numero_cajas': row['numero_cajas'],
                'cajas_enviadas': row['cajas_enviadas'], 'cajas_disponibles': row['numero_cajas'] - row['cajas_enviadas'],
                'merma_kilos': row.get('merma_kilos', 0), 'porcentaje_merma': row.get('porcentaje_merma', 0),
                'observaciones': row.get('observaciones', '')
            })
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

# ==========================================
# FUNCIONES PARA CAJAS DISPONIBLES
# ==========================================
def get_cajas_disponibles_por_invernadero(invernadero_id):
    try:
        result = supabase.table('cosechas').select('numero_cajas, cajas_enviadas').eq('invernadero_id', invernadero_id).execute()
        disponibles = sum(row['numero_cajas'] - row['cajas_enviadas'] for row in result.data)
        return disponibles
    except:
        return 0

def get_detalle_cajas_por_invernadero_presentacion(invernadero_id):
    try:
        result = supabase.table('cosechas').select('presentacion, numero_cajas, cajas_enviadas').eq('invernadero_id', invernadero_id).execute()
        resultados = {'6 oz': 0, '12 oz': 0}
        for row in result.data:
            disponibles = row['numero_cajas'] - row['cajas_enviadas']
            if row['presentacion'] in resultados:
                resultados[row['presentacion']] += disponibles
        return resultados
    except:
        return {'6 oz': 0, '12 oz': 0}

# ==========================================
# FUNCIONES DE TRASLADOS A CÁMARA FRÍA
# ==========================================
def registrar_traslado_camara_fria(invernadero_id, cantidad_cajas, trabajador_envia_id, recolector_id, tipo_envio, presentacion, lote, observaciones):
    try:
        fecha_actual = get_mexico_date()
        hora_actual = get_mexico_time().strftime("%H:%M:%S")
        semana_actual = get_mexico_week()
        supabase.table('traslados_camara_fria').insert({
            'fecha': fecha_actual.isoformat(), 'hora': hora_actual, 'semana': semana_actual,
            'invernadero_id': invernadero_id, 'trabajador_id': trabajador_envia_id, 'recolector_id': recolector_id,
            'tipo_envio': tipo_envio, 'presentacion': presentacion, 'cantidad_cajas': cantidad_cajas,
            'lote': lote if lote else None, 'observaciones': observaciones if observaciones else None
        }).execute()
        
        cosechas = supabase.table('cosechas').select('id, numero_cajas, cajas_enviadas').eq('invernadero_id', invernadero_id).eq('presentacion', presentacion).order('fecha', desc=True).order('id', desc=True).execute()
        cajas_restantes = cantidad_cajas
        for cosecha in cosechas.data:
            if cajas_restantes <= 0:
                break
            disponibles = cosecha['numero_cajas'] - cosecha['cajas_enviadas']
            if disponibles > 0:
                a_enviar = min(disponibles, cajas_restantes)
                supabase.table('cosechas').update({'cajas_enviadas': cosecha['cajas_enviadas'] + a_enviar}).eq('id', cosecha['id']).execute()
                cajas_restantes -= a_enviar
        invalidar_cache()
        return True, f"✅ Traslado registrado correctamente"
    except Exception as e:
        return False, f"❌ Error al registrar: {str(e)}"

def get_traslados_camara_fria(fecha_inicio=None, fecha_fin=None, invernadero_id=None):
    try:
        query = supabase.table('traslados_camara_fria').select("""
            *, invernaderos:invernadero_id (nombre), trabajadores:trabajador_id (nombre, apellido_paterno),
            recolectores:recolector_id (nombre, apellido_paterno)
        """)
        if fecha_inicio:
            query = query.gte('fecha', fecha_inicio.isoformat() if isinstance(fecha_inicio, date) else fecha_inicio)
        if fecha_fin:
            query = query.lte('fecha', fecha_fin.isoformat() if isinstance(fecha_fin, date) else fecha_fin)
        if invernadero_id:
            query = query.eq('invernadero_id', invernadero_id)
        result = query.order('fecha', desc=True).order('hora', desc=True).execute()
        data = []
        for row in result.data:
            trabajador_envia = f"{row['trabajadores'].get('nombre', '')} {row['trabajadores'].get('apellido_paterno', '')}" if row['trabajadores'] else ""
            recolector = f"{row['recolectores'].get('nombre', '')} {row['recolectores'].get('apellido_paterno', '')}" if row['recolectores'] else ""
            data.append({
                'id': row['id'], 'fecha': row['fecha'], 'hora': row['hora'], 'semana': row['semana'],
                'invernadero_id': row['invernadero_id'], 'invernadero': row['invernaderos']['nombre'] if row['invernaderos'] else 'Desconocido',
                'trabajador_id': row['trabajador_id'], 'trabajador_envia': trabajador_envia, 'recolector': recolector,
                'tipo_envio': row['tipo_envio'], 'presentacion': row['presentacion'], 'cantidad_cajas': row['cantidad_cajas'],
                'lote': row.get('lote', ''), 'observaciones': row.get('observaciones', '')
            })
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

# ==========================================
# FUNCIONES DE PESAJE DE CAJAS
# ==========================================
def registrar_pesaje_cajas(traslado_id, invernadero_id, trabajador_id, presentacion, cantidad_pesadas, cajas_recibidas, nota):
    try:
        fecha_actual = get_mexico_date()
        hora_actual = get_mexico_time().strftime("%H:%M:%S")
        semana_actual = get_mexico_week()
        diferencia = cantidad_pesadas - cajas_recibidas
        supabase.table('pesaje_cajas').insert({
            'fecha': fecha_actual.isoformat(), 'hora': hora_actual, 'semana': semana_actual,
            'traslado_id': traslado_id, 'invernadero_id': invernadero_id, 'trabajador_id': trabajador_id,
            'presentacion': presentacion, 'cantidad_cajas_pesadas': cantidad_pesadas,
            'cajas_recibidas': cajas_recibidas, 'diferencia': diferencia, 'nota': nota
        }).execute()
        invalidar_cache()
        if diferencia != 0:
            return True, f"✅ Pesaje registrado - Diferencia de {abs(diferencia)} cajas ({'faltan' if diferencia < 0 else 'sobran'})"
        return True, f"✅ Pesaje registrado - Coincidencia perfecta"
    except Exception as e:
        return False, f"❌ Error al registrar pesaje: {str(e)}"

def get_pesajes(fecha_inicio=None, fecha_fin=None, invernadero_id=None):
    try:
        query = supabase.table('pesaje_cajas').select("""
            *, invernaderos:invernadero_id (nombre), trabajadores:trabajador_id (nombre, apellido_paterno)
        """)
        if fecha_inicio:
            query = query.gte('fecha', fecha_inicio.isoformat())
        if fecha_fin:
            query = query.lte('fecha', fecha_fin.isoformat())
        if invernadero_id:
            query = query.eq('invernadero_id', invernadero_id)
        result = query.order('fecha', desc=True).execute()
        data = []
        for row in result.data:
            data.append({
                'fecha': row['fecha'], 'hora': row['hora'], 'invernadero': row['invernaderos']['nombre'] if row['invernaderos'] else '',
                'pesador': f"{row['trabajadores']['nombre']} {row['trabajadores']['apellido_paterno']}" if row['trabajadores'] else '',
                'presentacion': row['presentacion'], 'cajas_pesadas': row['cantidad_cajas_pesadas'],
                'cajas_recibidas': row['cajas_recibidas'], 'diferencia': row['diferencia'], 'nota': row.get('nota', '')
            })
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

# ==========================================
# FUNCIONES DE CAJAS EN MESA
# ==========================================
def registrar_cajas_mesa(invernadero_id, trabajador_id, cantidad_cajas, presentacion, solicitando_apoyo, observaciones):
    try:
        fecha_actual = get_mexico_date()
        hora_actual = get_mexico_time().strftime("%H:%M:%S")
        supabase.table('cajas_mesa').insert({
            'fecha': fecha_actual.isoformat(), 'hora': hora_actual, 'invernadero_id': invernadero_id,
            'trabajador_id': trabajador_id, 'cantidad_cajas': cantidad_cajas, 'presentacion': presentacion,
            'solicitando_apoyo': solicitando_apoyo, 'observaciones': observaciones
        }).execute()
        invalidar_cache()
        if solicitando_apoyo:
            return True, "✅ Registro guardado - Se ha notificado la solicitud de apoyo"
        return True, "✅ Registro guardado correctamente"
    except Exception as e:
        return False, f"❌ Error al registrar: {str(e)}"

def get_cajas_mesa(fecha=None, solo_pendientes=True):
    try:
        query = supabase.table('cajas_mesa').select("""
            *, invernaderos:invernadero_id (nombre), trabajadores:trabajador_id (nombre, apellido_paterno)
        """)
        if fecha:
            query = query.eq('fecha', fecha.isoformat())
        if solo_pendientes:
            query = query.eq('atendido', False)
        result = query.order('created_at', desc=True).execute()
        data = []
        for row in result.data:
            data.append({
                'id': row['id'], 'fecha': row['fecha'], 'hora': row['hora'],
                'invernadero': row['invernaderos']['nombre'] if row['invernaderos'] else '',
                'trabajador': f"{row['trabajadores']['nombre']} {row['trabajadores']['apellido_paterno']}" if row['trabajadores'] else '',
                'cantidad_cajas': row['cantidad_cajas'], 'presentacion': row['presentacion'],
                'solicita_apoyo': row['solicitando_apoyo'], 'atendido': row['atendido'], 'observaciones': row.get('observaciones', '')
            })
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

def marcar_atendido_caja_mesa(caja_id, atendido_por):
    try:
        supabase.table('cajas_mesa').update({'atendido': True, 'atendido_por': atendido_por}).eq('id', caja_id).execute()
        invalidar_cache()
        return True, "✅ Solicitud marcada como atendida"
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

# ==========================================
# FUNCIONES DE CONTROL DE ASISTENCIA
# ==========================================
def registrar_evento_asistencia(trabajador_id, invernadero_id, tipo_evento):
    try:
        fecha_actual = get_mexico_date()
        hora_actual = get_mexico_time().strftime("%H:%M:%S")
        
        if tipo_evento == 'entrada_invernadero':
            registro_activo = supabase.table('asistencia').select('*').eq('trabajador_id', trabajador_id).eq('fecha', fecha_actual.isoformat()).neq('estado', 'finalizado').order('id', desc=True).limit(1).execute()
            if registro_activo.data:
                reg = registro_activo.data[0]
                if reg.get('invernadero_id') != invernadero_id:
                    return False, "❌ Tienes un registro activo en otro invernadero. Primero debes registrar salida."
                return False, "❌ Ya tienes un registro activo hoy"
            
            supabase.table('asistencia').insert({
                'trabajador_id': trabajador_id, 'invernadero_id': invernadero_id, 'fecha': fecha_actual.isoformat(),
                'hora_entrada': hora_actual, 'estado': 'activo', 'tipo_movimiento': tipo_evento
            }).execute()
            supabase.table('registros_asistencia').insert({
                'trabajador_id': trabajador_id, 'invernadero_id': invernadero_id, 'fecha': fecha_actual.isoformat(),
                'hora': hora_actual, 'tipo_evento': tipo_evento
            }).execute()
            
        elif tipo_evento == 'salida_invernadero':
            registro_activo = supabase.table('asistencia').select('*').eq('trabajador_id', trabajador_id).eq('fecha', fecha_actual.isoformat()).neq('estado', 'finalizado').order('id', desc=True).limit(1).execute()
            if not registro_activo.data:
                return False, "❌ No hay registro de entrada activo"
            reg = registro_activo.data[0]
            if reg.get('hora_entrada') is None:
                return False, "❌ Primero debes registrar entrada"
            if reg.get('hora_salida') is not None:
                return False, "❌ Ya registraste salida"
            
            supabase.table('asistencia').update({'hora_salida': hora_actual, 'estado': 'finalizado', 'tipo_movimiento': tipo_evento}).eq('id', reg['id']).execute()
            supabase.table('registros_asistencia').insert({
                'trabajador_id': trabajador_id, 'invernadero_id': reg.get('invernadero_id'), 'fecha': fecha_actual.isoformat(),
                'hora': hora_actual, 'tipo_evento': tipo_evento
            }).execute()
            
        elif tipo_evento == 'salida_comer':
            registro_activo = supabase.table('asistencia').select('*').eq('trabajador_id', trabajador_id).eq('fecha', fecha_actual.isoformat()).neq('estado', 'finalizado').order('id', desc=True).limit(1).execute()
            if not registro_activo.data:
                return False, "❌ No hay registro de entrada activo"
            reg = registro_activo.data[0]
            if reg.get('hora_entrada') is None:
                return False, "❌ Primero debes registrar entrada"
            if reg.get('hora_salida_comida') is not None:
                return False, "❌ Ya registraste salida a comer"
            
            supabase.table('asistencia').update({'hora_salida_comida': hora_actual, 'estado': 'comida', 'tipo_movimiento': tipo_evento}).eq('id', reg['id']).execute()
            supabase.table('registros_asistencia').insert({
                'trabajador_id': trabajador_id, 'invernadero_id': reg.get('invernadero_id'), 'fecha': fecha_actual.isoformat(),
                'hora': hora_actual, 'tipo_evento': tipo_evento
            }).execute()
            
        elif tipo_evento == 'regreso_comida':
            registro_activo = supabase.table('asistencia').select('*').eq('trabajador_id', trabajador_id).eq('fecha', fecha_actual.isoformat()).neq('estado', 'finalizado').order('id', desc=True).limit(1).execute()
            if not registro_activo.data:
                return False, "❌ No hay registro de entrada activo"
            reg = registro_activo.data[0]
            if reg.get('hora_salida_comida') is None:
                return False, "❌ Primero debes registrar salida a comer"
            if reg.get('hora_entrada_comida') is not None:
                return False, "❌ Ya registraste regreso de comida"
            
            supabase.table('asistencia').update({'hora_entrada_comida': hora_actual, 'estado': 'activo', 'tipo_movimiento': tipo_evento}).eq('id', reg['id']).execute()
            supabase.table('registros_asistencia').insert({
                'trabajador_id': trabajador_id, 'invernadero_id': reg.get('invernadero_id'), 'fecha': fecha_actual.isoformat(),
                'hora': hora_actual, 'tipo_evento': tipo_evento
            }).execute()
        
        invalidar_cache()
        mensajes = {'entrada_invernadero': "✅ Entrada registrada correctamente", 'salida_invernadero': "✅ Salida registrada correctamente", 
                    'salida_comer': "✅ Salida a comer registrada", 'regreso_comida': "✅ Regreso de comida registrado"}
        return True, mensajes.get(tipo_evento, "✅ Evento registrado correctamente")
    except Exception as e:
        return False, f"❌ Error al registrar: {str(e)}"

def get_estado_asistencia_actual(trabajador_id):
    try:
        fecha_actual = get_mexico_date()
        result = supabase.table('asistencia').select("*, invernaderos:invernadero_id (nombre)").eq('trabajador_id', trabajador_id).eq('fecha', fecha_actual.isoformat()).neq('estado', 'finalizado').order('id', desc=True).limit(1).execute()
        if result.data:
            reg = result.data[0]
            return {
                'id': reg['id'], 'estado': reg['estado'], 'hora_entrada': reg.get('hora_entrada'),
                'hora_salida_comida': reg.get('hora_salida_comida'), 'hora_entrada_comida': reg.get('hora_entrada_comida'),
                'hora_salida': reg.get('hora_salida'), 'invernadero': reg['invernaderos']['nombre'] if reg.get('invernaderos') else None
            }
        return None
    except:
        return None

def get_registros_asistencia(filtros=None):
    try:
        query = supabase.table('registros_asistencia').select("""
            *, trabajadores:trabajador_id (nombre, apellido_paterno), invernaderos:invernadero_id (nombre)
        """)
        if filtros:
            if filtros.get('trabajador_id'):
                query = query.eq('trabajador_id', filtros['trabajador_id'])
            if filtros.get('fecha_inicio'):
                query = query.gte('fecha', filtros['fecha_inicio'].isoformat() if isinstance(filtros['fecha_inicio'], date) else filtros['fecha_inicio'])
            if filtros.get('fecha_fin'):
                query = query.lte('fecha', filtros['fecha_fin'].isoformat() if isinstance(filtros['fecha_fin'], date) else filtros['fecha_fin'])
            if filtros.get('tipo_evento') and filtros.get('tipo_evento') != "Todos":
                query = query.eq('tipo_evento', filtros['tipo_evento'])
        result = query.order('fecha', desc=True).order('hora', desc=True).execute()
        data = []
        for row in result.data:
            trabajador = f"{row['trabajadores'].get('nombre', '')} {row['trabajadores'].get('apellido_paterno', '')}" if row['trabajadores'] else ""
            tipo_evento_display = {'entrada_invernadero': 'Entrada a Invernadero', 'salida_comer': 'Salida a Comer', 
                                   'regreso_comida': 'Regreso de Comida', 'salida_invernadero': 'Salida'}.get(row['tipo_evento'], row['tipo_evento'])
            data.append({
                'id': row['id'], 'trabajador': trabajador, 'trabajador_id': row['trabajador_id'],
                'invernadero': row['invernaderos']['nombre'] if row['invernaderos'] else None,
                'fecha': row['fecha'], 'hora': row['hora'], 'tipo_evento': tipo_evento_display,
                'fecha_registro': f"{row['fecha']} {row['hora']}"
            })
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

def get_resumen_asistencia_dia(fecha=None):
    if not fecha:
        fecha = get_mexico_date()
    try:
        trabajadores = get_all_workers()
        asistencias = supabase.table('asistencia').select("*, invernaderos:invernadero_id (nombre)").eq('fecha', fecha.isoformat()).execute()
        asis_dict = {row['trabajador_id']: row for row in asistencias.data}
        descansos = supabase.table('descansos').select('*').eq('fecha', fecha.isoformat()).execute()
        descansos_dict = {row['trabajador_id']: row for row in descansos.data}
        incidencias = supabase.table('incidencias').select('*').eq('fecha', fecha.isoformat()).execute()
        incidencias_dict = {row['trabajador_id']: row for row in incidencias.data}
        data = []
        for _, trabajador in trabajadores.iterrows():
            trabajador_id = trabajador['id']
            asistencia = asis_dict.get(trabajador_id, {})
            descanso = descansos_dict.get(trabajador_id)
            incidencia = incidencias_dict.get(trabajador_id)
            estado_actual = ""
            if descanso:
                estado_actual = 'Descanso'
            elif incidencia:
                estado_actual = f"Incidencia: {incidencia.get('tipo_incidencia', '')}"
            elif not asistencia.get('hora_entrada'):
                estado_actual = 'Falta'
            elif not asistencia.get('hora_salida'):
                estado_actual = 'En invernadero'
            elif asistencia.get('hora_salida_comida') and not asistencia.get('hora_entrada_comida'):
                estado_actual = 'En comida'
            else:
                estado_actual = 'Finalizado'
            data.append({
                'trabajador_id': trabajador_id, 'trabajador': f"{trabajador['nombre']} {trabajador['apellido_paterno']}",
                'hora_entrada': asistencia.get('hora_entrada'), 'hora_salida_comida': asistencia.get('hora_salida_comida'),
                'hora_entrada_comida': asistencia.get('hora_entrada_comida'), 'hora_salida': asistencia.get('hora_salida'),
                'invernadero': asistencia.get('invernaderos', {}).get('nombre') if asistencia.get('invernaderos') else None,
                'estado_actual': estado_actual
            })
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

# ==========================================
# FUNCIONES DE DESCANSO E INCIDENCIAS
# ==========================================
def registrar_descanso(trabajador_id, fecha, tipo_descanso, observaciones=""):
    try:
        supabase.table('descansos').upsert({'trabajador_id': trabajador_id, 'fecha': fecha.isoformat() if isinstance(fecha, date) else fecha, 
                                            'tipo_descanso': tipo_descanso, 'observaciones': observaciones}).execute()
        invalidar_cache()
        return True, f"✅ Descanso registrado: {tipo_descanso}"
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

def get_descansos(fecha_inicio=None, fecha_fin=None):
    try:
        query = supabase.table('descansos').select("*, trabajadores:trabajador_id (nombre, apellido_paterno)")
        if fecha_inicio:
            query = query.gte('fecha', fecha_inicio.isoformat() if isinstance(fecha_inicio, date) else fecha_inicio)
        if fecha_fin:
            query = query.lte('fecha', fecha_fin.isoformat() if isinstance(fecha_fin, date) else fecha_fin)
        result = query.order('fecha', desc=True).execute()
        data = []
        for row in result.data:
            trabajador = f"{row['trabajadores'].get('nombre', '')} {row['trabajadores'].get('apellido_paterno', '')}" if row['trabajadores'] else ""
            data.append({'id': row['id'], 'trabajador_id': row['trabajador_id'], 'trabajador': trabajador, 
                        'fecha': row['fecha'], 'tipo_descanso': row['tipo_descanso'], 'observaciones': row.get('observaciones', '')})
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

def registrar_incidencia(trabajador_id, fecha, tipo_incidencia, subtipo, horas_afectadas, justificada, observaciones, registrado_por):
    try:
        supabase.table('incidencias').insert({
            'trabajador_id': trabajador_id, 'fecha': fecha.isoformat() if isinstance(fecha, date) else fecha,
            'tipo_incidencia': tipo_incidencia, 'subtipo': subtipo, 'horas_afectadas': horas_afectadas,
            'justificada': justificada, 'observaciones': observaciones, 'registrado_por': registrado_por
        }).execute()
        invalidar_cache()
        return True, f"✅ Incidencia registrada: {tipo_incidencia}"
    except Exception as e:
        return False, f"❌ Error al registrar: {str(e)}"

def get_incidencias(fecha_inicio=None, fecha_fin=None, trabajador_id=None):
    try:
        query = supabase.table('incidencias').select("*, trabajadores:trabajador_id (nombre, apellido_paterno)")
        if fecha_inicio:
            query = query.gte('fecha', fecha_inicio.isoformat() if isinstance(fecha_inicio, date) else fecha_inicio)
        if fecha_fin:
            query = query.lte('fecha', fecha_fin.isoformat() if isinstance(fecha_fin, date) else fecha_fin)
        if trabajador_id:
            query = query.eq('trabajador_id', trabajador_id)
        result = query.order('fecha', desc=True).order('created_at', desc=True).execute()
        data = []
        for row in result.data:
            trabajador = f"{row['trabajadores'].get('nombre', '')} {row['trabajadores'].get('apellido_paterno', '')}" if row['trabajadores'] else ""
            data.append({
                'id': row['id'], 'trabajador_id': row['trabajador_id'], 'trabajador': trabajador,
                'fecha': row['fecha'], 'tipo_incidencia': row['tipo_incidencia'], 'subtipo': row.get('subtipo'),
                'horas_afectadas': row.get('horas_afectadas', 0), 'justificada': row.get('justificada', False),
                'observaciones': row.get('observaciones', ''), 'registrado_por': row.get('registrado_por', '')
            })
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

# ==========================================
# FUNCIONES DE MERMA
# ==========================================
def registrar_merma(invernadero_id, supervisor_nombre, kilos_merma, tipo_merma, observaciones, registrado_por):
    try:
        fecha_actual = get_mexico_date()
        hora_actual = get_mexico_time().strftime("%H:%M:%S")
        semana_actual = get_mexico_week()
        supabase.table('merma').insert({
            'fecha': fecha_actual.isoformat(), 'hora': hora_actual, 'semana': semana_actual,
            'invernadero_id': invernadero_id, 'supervisor_nombre': supervisor_nombre,
            'kilos_merma': kilos_merma, 'tipo_merma': tipo_merma, 'observaciones': observaciones,
            'registrado_por': registrado_por
        }).execute()
        invalidar_cache()
        return True, "✅ Merma registrada correctamente"
    except Exception as e:
        return False, f"❌ Error al registrar: {str(e)}"

def get_merma(fecha_inicio=None, fecha_fin=None, invernadero_id=None):
    try:
        query = supabase.table('merma').select("*, invernaderos:invernadero_id (nombre)")
        if fecha_inicio:
            query = query.gte('fecha', fecha_inicio.isoformat() if isinstance(fecha_inicio, date) else fecha_inicio)
        if fecha_fin:
            query = query.lte('fecha', fecha_fin.isoformat() if isinstance(fecha_fin, date) else fecha_fin)
        if invernadero_id:
            query = query.eq('invernadero_id', invernadero_id)
        result = query.order('fecha', desc=True).order('hora', desc=True).execute()
        data = []
        for row in result.data:
            data.append({
                'id': row['id'], 'fecha': row['fecha'], 'hora': row['hora'], 'semana': row['semana'],
                'invernadero_id': row['invernadero_id'], 'invernadero_nombre': row['invernaderos']['nombre'] if row['invernaderos'] else 'Desconocido',
                'supervisor_nombre': row['supervisor_nombre'], 'kilos_merma': row['kilos_merma'],
                'tipo_merma': row['tipo_merma'], 'observaciones': row.get('observaciones', ''),
                'registrado_por': row.get('registrado_por', '')
            })
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

def get_stats_merma(fecha_inicio=None, fecha_fin=None):
    merma = get_merma(fecha_inicio, fecha_fin)
    if merma.empty:
        return {'total_merma': 0, 'merma_por_invernadero': pd.DataFrame(), 'merma_por_tipo': pd.DataFrame(), 
                'merma_diaria': pd.DataFrame(), 'top_supervisores': pd.DataFrame()}
    total_merma = merma['kilos_merma'].sum() if 'kilos_merma' in merma.columns else 0
    merma_por_invernadero = merma.groupby('invernadero_nombre').agg({'kilos_merma': 'sum', 'id': 'count'}).rename(columns={'id': 'cantidad_registros'}).reset_index()
    if 'kilos_merma' in merma_por_invernadero.columns:
        merma_por_invernadero['promedio_merma'] = merma_por_invernadero['kilos_merma'] / merma_por_invernadero['cantidad_registros']
    merma_por_tipo = merma.groupby('tipo_merma').agg({'kilos_merma': 'sum', 'id': 'count'}).rename(columns={'id': 'cantidad_registros'}).reset_index()
    merma_diaria = merma.groupby('fecha').agg({'kilos_merma': 'sum', 'id': 'count'}).rename(columns={'id': 'registros'}).reset_index()
    top_supervisores = merma.groupby('supervisor_nombre').agg({'kilos_merma': 'sum', 'id': 'count'}).rename(columns={'id': 'cantidad_registros'}).reset_index().head(10)
    return {'total_merma': total_merma, 'merma_por_invernadero': merma_por_invernadero, 'merma_por_tipo': merma_por_tipo, 
            'merma_diaria': merma_diaria, 'top_supervisores': top_supervisores}

# ==========================================
# FUNCIONES DE PROYECCIONES
# ==========================================
PESO_CAJA = 2.16

def registrar_proyeccion(semana, cajas_proyectadas, registrado_por, observaciones=""):
    try:
        supabase.table('proyecciones_cajas').upsert({'semana': semana, 'cajas_proyectadas': cajas_proyectadas, 
                                                     'registrado_por': registrado_por, 'observaciones': observaciones}).execute()
        invalidar_cache()
        return True, f"✅ Proyección registrada para semana {semana}"
    except Exception as e:
        return False, f"❌ Error al registrar proyección: {str(e)}"

def get_proyecciones(semana=None):
    try:
        query = supabase.table('proyecciones_cajas').select('*')
        if semana:
            query = query.eq('semana', semana)
        result = query.order('semana', desc=True).execute()
        data = [{'id': row['id'], 'semana': row['semana'], 'cajas_proyectadas': row['cajas_proyectadas'], 
                 'fecha_registro': row['fecha_registro'], 'registrado_por': row.get('registrado_por', ''), 
                 'observaciones': row.get('observaciones', '')} for row in result.data]
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

def get_comparativa_proyeccion_real_con_filtros(semana_inicio=None, semana_fin=None, tipo_cosecha=None, presentacion=None):
    try:
        query_cosechas = supabase.table('cosechas').select('semana, numero_cajas')
        if semana_inicio:
            query_cosechas = query_cosechas.gte('semana', semana_inicio)
        if semana_fin:
            query_cosechas = query_cosechas.lte('semana', semana_fin)
        if tipo_cosecha and tipo_cosecha != "Todos":
            query_cosechas = query_cosechas.eq('tipo_cosecha', tipo_cosecha)
        if presentacion and presentacion != "Todos":
            query_cosechas = query_cosechas.eq('presentacion', presentacion)
        cosechas = query_cosechas.execute()
        real_dict = {}
        for row in cosechas.data:
            semana = row['semana']
            real_dict[semana] = real_dict.get(semana, 0) + row['numero_cajas']
        proyecciones = get_proyecciones()
        semanas = set(real_dict.keys()) | set(proyecciones['semana'].tolist() if not proyecciones.empty else [])
        semanas = sorted([s for s in semanas if s >= (semana_inicio or 1) and s <= (semana_fin or 52)])
        data = []
        for semana in semanas:
            cajas_reales = real_dict.get(semana, 0)
            cajas_proyectadas = proyecciones[proyecciones['semana'] == semana]['cajas_proyectadas'].iloc[0] if not proyecciones.empty and not proyecciones[proyecciones['semana'] == semana].empty else 0
            diferencia = cajas_reales - cajas_proyectadas
            porcentaje_desviacion = (diferencia / cajas_proyectadas * 100) if cajas_proyectadas > 0 else 0
            data.append({'semana': semana, 'cajas_proyectadas': cajas_proyectadas, 'cajas_reales': cajas_reales, 
                        'diferencia': diferencia, 'porcentaje_desviacion': porcentaje_desviacion, 
                        'estado': '✅ Superávit' if diferencia >= 0 else '⚠️ Déficit'})
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

def get_resumen_proyecciones_total_con_filtros_dashboard(df_cosechas):
    try:
        proyecciones = get_proyecciones()
        total_real = df_cosechas['numero_cajas'].sum() if not df_cosechas.empty else 0
        total_proyectado = proyecciones['cajas_proyectadas'].sum() if not proyecciones.empty else 0
        diferencia = total_real - total_proyectado
        porcentaje = (diferencia / total_proyectado * 100) if total_proyectado > 0 else 0
        return {'total_proyectado': total_proyectado, 'total_real': total_real, 'diferencia': diferencia, 'porcentaje_desviacion': porcentaje}
    except:
        return {'total_proyectado': 0, 'total_real': 0, 'diferencia': 0, 'porcentaje_desviacion': 0}

# ==========================================
# FUNCIONES DE CIERRE DE DÍA Y AUDITORÍA
# ==========================================
def generar_reporte_auditoria_dia(fecha):
    try:
        cosechas = get_cosechas(fecha_inicio=fecha, fecha_fin=fecha)
        traslados = get_traslados_camara_fria(fecha_inicio=fecha, fecha_fin=fecha)
        pesajes = get_pesajes(fecha_inicio=fecha, fecha_fin=fecha)
        merma = get_merma(fecha_inicio=fecha, fecha_fin=fecha)
        asistencia = get_registros_asistencia({'fecha_inicio': fecha, 'fecha_fin': fecha})
        avance = get_avance_hoy_por_invernadero()
        cajas_mesa = get_cajas_mesa(fecha=fecha, solo_pendientes=False)
        incidencias = get_incidencias(fecha_inicio=fecha, fecha_fin=fecha)
        
        reporte = {
            'fecha': fecha.isoformat(),
            'generado_por': st.session_state.get('user_nombre', 'Sistema'),
            'resumen': {
                'total_cajas_cosechadas': float(cosechas['numero_cajas'].sum() if not cosechas.empty else 0),
                'total_cajas_trasladadas': float(traslados['cantidad_cajas'].sum() if not traslados.empty else 0),
                'total_cajas_pesadas': float(pesajes['cajas_pesadas'].sum() if not pesajes.empty else 0),
                'total_cajas_recibidas': float(pesajes['cajas_recibidas'].sum() if not pesajes.empty else 0),
                'diferencia_pesaje': float(pesajes['cajas_pesadas'].sum() - pesajes['cajas_recibidas'].sum() if not pesajes.empty else 0),
                'total_merma_kilos': float(merma['kilos_merma'].sum() if not merma.empty else 0),
                'total_personal_asistencia': asistencia['trabajador'].nunique() if not asistencia.empty else 0,
                'promedio_avance': float(avance['porcentaje'].mean() if not avance.empty else 0),
                'total_incidencias': len(incidencias) if not incidencias.empty else 0,
                'total_solicitudes_apoyo': len(cajas_mesa[cajas_mesa['solicita_apoyo'] == True]) if not cajas_mesa.empty else 0
            }
        }
        return reporte
    except Exception as e:
        st.error(f"Error al generar reporte: {str(e)}")
        return None

def registrar_cierre_dia(fecha, cerrado_por):
    try:
        existente = supabase.table('cierres_dia').select('id').eq('fecha', fecha.isoformat()).execute()
        if existente.data:
            return False, "❌ Este día ya fue cerrado anteriormente"
        reporte = generar_reporte_auditoria_dia(fecha)
        if reporte:
            supabase.table('cierres_dia').insert({'fecha': fecha.isoformat(), 'cerrado_por': cerrado_por, 'reporte': reporte}).execute()
            invalidar_cache()
            return True, "✅ Cierre de día registrado exitosamente"
        return False, "❌ Error al generar el reporte"
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

def get_cierres_dia():
    try:
        result = supabase.table('cierres_dia').select('*').order('fecha', desc=True).execute()
        return pd.DataFrame([{'fecha': row['fecha'], 'cerrado_por': row['cerrado_por'], 'created_at': row['created_at']} for row in result.data])
    except:
        return pd.DataFrame()

# ==========================================
# FUNCIONES DE QR Y ESCANEO
# ==========================================
def procesar_qr_data(qr_data):
    try:
        id_match = re.search(r'[?&]id=([^&]+)', qr_data)
        nombre_match = re.search(r'[?&]nombre=([^&]+)', qr_data)
        if id_match and nombre_match:
            return id_match.group(1), nombre_match.group(1).replace('%20', ' ').replace('+', ' ')
        if '|' in qr_data:
            partes = qr_data.split('|')
            if len(partes) >= 2:
                return partes[0], partes[1]
        return None, None
    except:
        return None, None

def generar_qr_trabajador_simple(id_trabajador, nombre, url_base="http://localhost:8501"):
    url = f"{url_base}?id={id_trabajador}&nombre={nombre.replace(' ', '%20')}"
    qr = qrcode.QRCode(version=1, box_size=10, border=5, error_correction=qrcode.constants.ERROR_CORRECT_L)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    return img_bytes

# ==========================================
# FUNCIÓN DE ESCANEO QR CON CÁMARA (SIMPLIFICADA)
# ==========================================
def escanear_qr_con_camara(tipo_evento="asistencia", mostrar_invernadero=False):
    st.markdown("### 📷 Escaneo con Cámara")
    
    if 'scanned_worker' not in st.session_state:
        st.session_state.scanned_worker = None
    if 'show_form' not in st.session_state:
        st.session_state.show_form = False
    
    if st.button("🔄 Nuevo Escaneo", use_container_width=True):
        st.session_state.scanned_worker = None
        st.session_state.show_form = False
        st.rerun()
    
    if not st.session_state.show_form:
        camera_image = st.camera_input("📸 Enfoca el código QR", key="qr_camera")
        if camera_image:
            image = Image.open(camera_image)
            img_array = np.array(image)
            qr_codes = decode(img_array)
            if qr_codes:
                for qr in qr_codes:
                    qr_data = qr.data.decode('utf-8')
                    id_trabajador, nombre = procesar_qr_data(qr_data)
                    if id_trabajador and nombre:
                        trabajador = get_worker_by_id(id_trabajador)
                        if trabajador:
                            st.session_state.scanned_worker = {'id': id_trabajador, 'nombre': nombre, 'data': trabajador}
                            st.session_state.show_form = True
                            st.rerun()
                        else:
                            st.error(f"❌ Trabajador no encontrado: {nombre}")
                    else:
                        st.error("❌ QR no válido")
            else:
                st.warning("📷 No se detectó QR")
    
    if st.session_state.show_form and st.session_state.scanned_worker:
        trabajador = st.session_state.scanned_worker
        st.success(f"✅ QR Detectado: {trabajador['nombre']}")
        
        if tipo_evento == "cosecha":
            st.markdown("### 📋 Registrar Cosecha")
            fecha_actual = get_mexico_date()
            dia_espanol = get_mexico_day_spanish()
            
            col1, col2 = st.columns(2)
            with col1:
                tipo_cosecha = st.radio("Tipo:", ["Nacional", "Exportación"], horizontal=True)
                if tipo_cosecha == "Nacional":
                    calidad = st.selectbox("Calidad:", ["Salmon", "Sobretono"])
                else:
                    calidad = None
            with col2:
                if tipo_cosecha == "Exportación":
                    presentacion = st.selectbox("Presentación:", ["6 oz", "12 oz"])
                else:
                    presentacion = "6 oz"
                    st.info("✅ Presentación: 6 oz")
            
            cantidad_clams = st.number_input("🍓 Cantidad de Clams:", min_value=0.0, value=0.0, step=1.0)
            merma_kilos = st.number_input("🗑️ Merma (kilos):", min_value=0.0, value=0.0, step=0.5)
            
            if presentacion == "12 oz":
                cajas = cantidad_clams / 6 if cantidad_clams > 0 else 0
            else:
                cajas = cantidad_clams / 12 if cantidad_clams > 0 else 0
            st.metric("📦 Cajas a registrar", f"{cajas:.2f}")
            
            if st.button("💾 Guardar Cosecha", type="primary"):
                if cantidad_clams <= 0:
                    st.error("Ingrese cantidad válida")
                else:
                    invernaderos = get_invernaderos()
                    invernadero_id = invernaderos[0][0] if invernaderos else None
                    data = {
                        'fecha': fecha_actual, 'dia': dia_espanol, 'semana': get_mexico_week(),
                        'trabajador_id': int(trabajador['id']), 'invernadero_id': invernadero_id,
                        'tipo_cosecha': tipo_cosecha, 'calidad': calidad, 'presentacion': presentacion,
                        'cantidad_clams': float(cantidad_clams), 'merma_kilos': float(merma_kilos)
                    }
                    success, msg = guardar_cosecha(data)
                    if success:
                        st.success(msg)
                        st.balloons()
                        st.session_state.show_form = False
                        st.session_state.scanned_worker = None
                        st.rerun()
                    else:
                        st.error(msg)
        
        elif tipo_evento == "asistencia":
            st.markdown("### 📋 Registrar Asistencia")
            invernaderos = get_invernaderos()
            invernadero_id = invernaderos[0][0] if invernaderos else None
            
            tipo_evento_asist = st.selectbox("📌 Evento:", 
                ["entrada_invernadero", "salida_comer", "regreso_comida", "salida_invernadero"],
                format_func=lambda x: {'entrada_invernadero': '🚪 Entrada a Invernadero', 'salida_comer': '🍽️ Salida a Comer',
                                       'regreso_comida': '✅ Regreso de Comida', 'salida_invernadero': '🚪 Salida de Invernadero'}[x])
            
            if st.button("✅ Registrar", type="primary"):
                success, msg = registrar_evento_asistencia(int(trabajador['id']), invernadero_id, tipo_evento_asist)
                if success:
                    st.success(msg)
                    st.balloons()
                    st.session_state.show_form = False
                    st.session_state.scanned_worker = None
                    st.rerun()
                else:
                    st.error(msg)

# ==========================================
# FUNCIONES DE GESTIÓN DE USUARIOS
# ==========================================
def get_all_users():
    try:
        result = supabase.table('perfiles_usuario').select('*').execute()
        return pd.DataFrame(result.data) if result.data else pd.DataFrame()
    except:
        return pd.DataFrame()

def update_user_permissions(user_id, rol, permisos, invernaderos_asignados):
    try:
        supabase.table('perfiles_usuario').update({'rol': rol, 'permisos': permisos, 'invernaderos_asignados': invernaderos_asignados}).eq('id', user_id).execute()
        invalidar_cache()
        return True, "✅ Permisos actualizados correctamente"
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

def update_system_config(clave, valor):
    try:
        supabase.table('configuracion_sistema').update({'valor': valor}).eq('clave', clave).execute()
        invalidar_cache()
        return True
    except:
        return False

def mostrar_gestion_usuarios():
    st.header("👥 Gestión de Usuarios y Permisos")
    
    if st.session_state.get('user_rol') != 'admin':
        st.error("❌ No tienes permiso para acceder a esta sección")
        return
    
    tab1, tab2, tab3 = st.tabs(["📋 Usuarios", "👤 Crear Usuario", "⚙️ Configuración"])
    
    with tab1:
        usuarios = get_all_users()
        if not usuarios.empty:
            for _, usuario in usuarios.iterrows():
                with st.expander(f"{usuario['nombre']} - {usuario['email']} ({usuario['rol']})"):
                    col1, col2 = st.columns(2)
                    with col1:
                        nuevo_rol = st.selectbox("Rol", ["admin", "supervisor"], index=0 if usuario['rol'] == 'admin' else 1, key=f"rol_{usuario['id']}")
                        invernaderos = get_all_invernaderos()
                        invernaderos_asignados_actuales = usuario.get('invernaderos_asignados', [])
                        invernaderos_asignados = st.multiselect("Invernaderos asignados", [inv[1] for inv in invernaderos], 
                            default=[inv[1] for inv in invernaderos if str(inv[0]) in invernaderos_asignados_actuales], key=f"inv_{usuario['id']}")
                        invernaderos_ids = [str(inv[0]) for inv in invernaderos if inv[1] in invernaderos_asignados]
                    with col2:
                        st.markdown("**Permisos:**")
                        permisos_actuales = usuario.get('permisos', {})
                        permisos_lista = [
                            ("gestion_personal", "👥 Gestión Personal"), ("registro_cosecha", "🌾 Registro Cosecha"),
                            ("registro_asistencia", "🕐 Control Asistencia"), ("avance_cosecha", "📊 Avance Cosecha"),
                            ("traslado_camara_fria", "❄️ Traslado a Cámara Fría"), ("gestion_merma", "🗑️ Gestión Merma"),
                            ("proyecciones", "📈 Proyecciones"), ("generar_qr", "📱 Generar QR"), ("reportes", "📋 Reportes"),
                            ("catalogos", "📚 Catálogos"), ("gestion_invernaderos", "🏭 Gestión Invernaderos"),
                            ("dashboard", "📊 Dashboard"), ("pesaje_cajas", "⚖️ Pesaje Cajas"), ("cajas_mesa", "📦 Cajas en Mesa"),
                            ("cierre_dia", "🔒 Cierre de Día"), ("auditoria_diaria", "📊 Auditoría Diaria")
                        ]
                        nuevos_permisos = {}
                        for permiso_key, permiso_label in permisos_lista:
                            nuevos_permisos[permiso_key] = st.checkbox(permiso_label, value=permisos_actuales.get(permiso_key, False), key=f"perm_{usuario['id']}_{permiso_key}")
                    
                    if st.button("💾 Guardar Cambios", key=f"save_{usuario['id']}"):
                        success, msg = update_user_permissions(usuario['id'], nuevo_rol, nuevos_permisos, invernaderos_ids)
                        if success:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
        else:
            st.info("No hay usuarios registrados")
    
    with tab2:
        st.subheader("Crear Nuevo Usuario")
        col1, col2 = st.columns(2)
        with col1:
            nuevo_email = st.text_input("Email", key="nuevo_email")
            nueva_password = st.text_input("Contraseña", type="password", key="nueva_password")
            nuevo_nombre = st.text_input("Nombre completo", key="nuevo_nombre")
        with col2:
            nuevo_rol_crear = st.selectbox("Rol", ["supervisor", "admin"], key="nuevo_rol")
            invernaderos_todos = get_all_invernaderos()
            invernaderos_nuevo = st.multiselect("Invernaderos asignados", [inv[1] for inv in invernaderos_todos], key="invernaderos_nuevo")
            invernaderos_nuevo_ids = [str(inv[0]) for inv in invernaderos_todos if inv[1] in invernaderos_nuevo]
            
            st.markdown("**Permisos para el nuevo usuario:**")
            permisos_nuevo = {}
            for permiso_key, permiso_label in [("gestion_personal", "👥 Gestión Personal"), ("registro_cosecha", "🌾 Registro Cosecha"),
                ("registro_asistencia", "🕐 Control Asistencia"), ("avance_cosecha", "📊 Avance Cosecha"),
                ("traslado_camara_fria", "❄️ Traslado a Cámara Fría"), ("gestion_merma", "🗑️ Gestión Merma"),
                ("proyecciones", "📈 Proyecciones"), ("generar_qr", "📱 Generar QR"), ("reportes", "📋 Reportes"),
                ("catalogos", "📚 Catálogos"), ("gestion_invernaderos", "🏭 Gestión Invernaderos"), ("dashboard", "📊 Dashboard"),
                ("pesaje_cajas", "⚖️ Pesaje Cajas"), ("cajas_mesa", "📦 Cajas en Mesa"), ("cierre_dia", "🔒 Cierre de Día"),
                ("auditoria_diaria", "📊 Auditoría Diaria")]:
                permisos_nuevo[permiso_key] = st.checkbox(permiso_label, value=(nuevo_rol_crear == 'admin'), key=f"perm_nuevo_{permiso_key}")
        
        if st.button("✅ Crear Usuario", type="primary", use_container_width=True):
            if nuevo_email and nueva_password and nuevo_nombre:
                if len(nueva_password) < 6:
                    st.error("La contraseña debe tener al menos 6 caracteres")
                else:
                    result = register_user(nuevo_email, nueva_password, nuevo_nombre, nuevo_rol_crear, permisos_nuevo, invernaderos_nuevo_ids)
                    if result['success']:
                        st.success(result['message'])
                        st.balloons()
                        st.rerun()
                    else:
                        st.error(result['error'])
            else:
                st.error("Complete todos los campos")
    
    with tab3:
        st.subheader("Configuración del Sistema")
        registro_manual_asistencia = get_configuracion_sistema('registro_manual_asistencia')
        registro_manual_cosecha = get_configuracion_sistema('registro_manual_cosecha')
        
        nueva_asistencia = st.checkbox("Permitir registro manual de asistencia", value=registro_manual_asistencia)
        nueva_cosecha = st.checkbox("Permitir registro manual de cosecha", value=registro_manual_cosecha)
        
        if st.button("💾 Guardar Configuración"):
            update_system_config('registro_manual_asistencia', str(nueva_asistencia).lower())
            update_system_config('registro_manual_cosecha', str(nueva_cosecha).lower())
            st.success("✅ Configuración guardada")
            st.rerun()

# ==========================================
# INTERFAZ DE DASHBOARD
# ==========================================
def mostrar_dashboard_general():
    st.markdown('<div class="section-title">📊 Dashboard General</div>', unsafe_allow_html=True)
    
    try:
        # Obtener estadísticas básicas
        trabajadores = get_all_workers()
        total_activos = len(trabajadores) if not trabajadores.empty else 0
        
        cosechas = get_cosechas(fecha_inicio=get_mexico_date() - timedelta(days=30), fecha_fin=get_mexico_date())
        total_cajas = cosechas['numero_cajas'].sum() if not cosechas.empty else 0
        
        traslados = get_traslados_camara_fria(fecha_inicio=get_mexico_date() - timedelta(days=30), fecha_fin=get_mexico_date())
        total_trasladadas = traslados['cantidad_cajas'].sum() if not traslados.empty else 0
        
        incidencias = get_incidencias(fecha_inicio=get_mexico_date() - timedelta(days=30), fecha_fin=get_mexico_date())
        total_incidencias = len(incidencias) if not incidencias.empty else 0
        
        # KPIs
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f'<div class="kpi-card"><div>👥</div><div class="kpi-value">{total_activos}</div><div class="kpi-label">Personal Activo</div></div>', unsafe_allow_html=True)
        with col2:
            st.markdown(f'<div class="kpi-card"><div>📦</div><div class="kpi-value">{total_cajas:,.0f}</div><div class="kpi-label">Cajas Cosechadas (30d)</div></div>', unsafe_allow_html=True)
        with col3:
            st.markdown(f'<div class="kpi-card"><div>❄️</div><div class="kpi-value">{total_trasladadas:,.0f}</div><div class="kpi-label">Trasladadas a Frío</div></div>', unsafe_allow_html=True)
        with col4:
            st.markdown(f'<div class="kpi-card"><div>⚠️</div><div class="kpi-value">{total_incidencias}</div><div class="kpi-label">Incidencias (30d)</div></div>', unsafe_allow_html=True)
        
        # Gráfico de producción por semana
        if not cosechas.empty:
            st.subheader("📊 Producción por Semana")
            df_semanal = cosechas.groupby('semana')['numero_cajas'].sum().reset_index().sort_values('semana')
            fig = px.line(df_semanal, x='semana', y='numero_cajas', title='Cajas Cosechadas por Semana',
                         labels={'semana': 'Semana', 'numero_cajas': 'Cajas'})
            fig.update_traces(line=dict(color='#2a6b3c', width=3))
            fig.update_layout(plot_bgcolor='white', height=400)
            st.plotly_chart(fig, use_container_width=True)
        
        # Avance del día
        st.subheader("📈 Avance de Cosecha del Día")
        df_avance = get_avance_hoy_por_invernadero()
        if not df_avance.empty:
            st.dataframe(df_avance[['invernadero_nombre', 'lineas_cosechadas', 'lineas_totales', 'porcentaje', 'turno']], use_container_width=True)
            
            # Gráfico de avance
            fig = px.bar(df_avance, x='invernadero_nombre', y='porcentaje', 
                        title='Porcentaje de Avance por Invernadero',
                        labels={'invernadero_nombre': 'Invernadero', 'porcentaje': 'Porcentaje (%)'},
                        color='porcentaje', color_continuous_scale='Greens')
            fig.update_traces(texttemplate='%{y:.1f}%', textposition='outside')
            fig.update_layout(plot_bgcolor='white', height=400)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay registros de avance para el día de hoy")
            
    except Exception as e:
        st.error(f"Error al cargar el dashboard: {str(e)}")

# ==========================================
# INTERFAZ DE GESTIÓN PERSONAL
# ==========================================
def mostrar_gestion_personal():
    st.header("👥 Gestión de Trabajadores")
    
    tab1, tab2 = st.tabs(["📋 Lista de Trabajadores", "➕ Agregar Trabajador"])
    
    with tab1:
        trabajadores = get_all_workers()
        if not trabajadores.empty:
            st.dataframe(trabajadores[['nombre', 'apellido_paterno', 'apellido_materno', 'puesto', 'departamento', 'telefono']], use_container_width=True)
            
            # Opciones de edición/baja
            trabajador_seleccionado = st.selectbox("Seleccionar trabajador para editar/dar de baja", 
                trabajadores.apply(lambda x: f"{x['id']} - {x['nombre']} {x['apellido_paterno']}", axis=1))
            
            if trabajador_seleccionado:
                trabajador_id = int(trabajador_seleccionado.split(' - ')[0])
                trabajador = get_worker_by_id(trabajador_id)
                
                if trabajador:
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✏️ Editar Trabajador", use_container_width=True):
                            st.session_state['editando_trabajador'] = trabajador_id
                    with col2:
                        if st.button("🚫 Dar de Baja", use_container_width=True):
                            fecha_baja = st.date_input("Fecha de baja", get_mexico_date())
                            if st.button("Confirmar Baja"):
                                success, msg = dar_baja(trabajador_id, fecha_baja)
                                if success:
                                    st.success(msg)
                                    st.rerun()
                                else:
                                    st.error(msg)
                    
                    if st.session_state.get('editando_trabajador') == trabajador_id:
                        with st.form("editar_trabajador"):
                            nuevo_nombre = st.text_input("Nombre", trabajador['nombre'])
                            nuevo_apellido_p = st.text_input("Apellido Paterno", trabajador['apellido_paterno'])
                            nuevo_apellido_m = st.text_input("Apellido Materno", trabajador['apellido_materno'])
                            nuevo_telefono = st.text_input("Teléfono", trabajador['telefono'] or '')
                            nuevo_correo = st.text_input("Correo", trabajador['correo'] or '')
                            
                            departamentos = get_departamentos_nombres()
                            nuevo_departamento = st.selectbox("Departamento", departamentos, 
                                index=departamentos.index(trabajador['departamento_nombre']) if trabajador['departamento_nombre'] in departamentos else 0)
                            
                            puestos = get_puestos_nombres()
                            nuevo_puesto = st.selectbox("Puesto", puestos,
                                index=puestos.index(trabajador['puesto_nombre']) if trabajador['puesto_nombre'] in puestos else 0)
                            
                            if st.form_submit_button("💾 Guardar Cambios"):
                                data = {
                                    'nombre': nuevo_nombre, 'apellido_paterno': nuevo_apellido_p,
                                    'apellido_materno': nuevo_apellido_m, 'telefono': nuevo_telefono,
                                    'correo': nuevo_correo, 'departamento': nuevo_departamento,
                                    'puesto': nuevo_puesto, 'tipo_nomina': trabajador['tipo_nomina'], 'estatus': 'activo'
                                }
                                success, msg = update_worker(trabajador_id, data)
                                if success:
                                    st.success(msg)
                                    del st.session_state['editando_trabajador']
                                    st.rerun()
                                else:
                                    st.error(msg)
        else:
            st.info("No hay trabajadores registrados")
    
    with tab2:
        with st.form("nuevo_trabajador"):
            col1, col2 = st.columns(2)
            with col1:
                nombre = st.text_input("Nombre *")
                apellido_paterno = st.text_input("Apellido Paterno *")
                apellido_materno = st.text_input("Apellido Materno")
                telefono = st.text_input("Teléfono")
            with col2:
                correo = st.text_input("Correo Electrónico")
                fecha_alta = st.date_input("Fecha de Alta", get_mexico_date())
                departamento = st.selectbox("Departamento *", get_departamentos_nombres())
                puesto = st.selectbox("Puesto *", get_puestos_nombres())
                tipo_nomina = st.selectbox("Tipo de Nómina", ["especial", "imss"])
            
            if st.form_submit_button("💾 Guardar Trabajador", type="primary"):
                if nombre and apellido_paterno and departamento and puesto:
                    data = {
                        'ap': apellido_paterno.strip().upper(), 'am': apellido_materno.strip().upper() if apellido_materno else None,
                        'nom': nombre.strip().upper(), 'cor': correo.strip() if correo else None,
                        'tel': telefono.strip() if telefono else None, 'fa': fecha_alta,
                        'departamento': departamento, 'tn': tipo_nomina, 'puesto': puesto
                    }
                    success, msg = add_worker(data)
                    if success:
                        st.success(msg)
                        st.balloons()
                        st.rerun()
                    else:
                        st.error(msg)
                else:
                    st.error("Complete los campos obligatorios (*)")

# ==========================================
# MENÚ LATERAL
# ==========================================
def mostrar_menu_sidebar():
    st.sidebar.markdown('<div class="sidebar-title"><h2>🌾 Sistema Integral</h2><p>Gestión Agrícola</p></div>', unsafe_allow_html=True)
    
    if st.session_state.get('authenticated', False):
        st.sidebar.markdown(f'<div class="user-info">👤 <strong>{st.session_state.get("user_nombre", "Usuario")}</strong><br>📧 {st.session_state.get("user_email", "")}<br>🎭 Rol: <strong>{st.session_state.get("user_rol", "supervisor").upper()}</strong></div>', unsafe_allow_html=True)
    
    permisos = st.session_state.get('user_permisos', {})
    
    menu_options = {}
    
    if permisos.get('dashboard', True):
        menu_options["📊 Dashboard"] = "Estadísticas generales"
    if permisos.get('registro_cosecha', True):
        menu_options["🌾 Registro Cosecha"] = "Registrar producción"
    if permisos.get('registro_asistencia', True):
        menu_options["🕐 Control Asistencia"] = "Registro entrada/salida"
    if permisos.get('avance_cosecha', True):
        menu_options["📊 Avance Cosecha"] = "Registrar avance por invernadero"
    if permisos.get('traslado_camara_fria', True):
        menu_options["❄️ Traslado a Cámara Fría"] = "Cajas a cámara fría y pesaje"
    if permisos.get('gestion_merma', True):
        menu_options["🗑️ Gestión Merma"] = "Registro de merma"
    if permisos.get('cajas_mesa', True):
        menu_options["📦 Cajas en Mesa"] = "Registro de cajas y solicitudes"
    if permisos.get('proyecciones', True):
        menu_options["📈 Proyecciones"] = "Comparativa real vs proyectado"
    if permisos.get('reportes', True):
        menu_options["📋 Reportes"] = "Reportes y estadísticas"
    if permisos.get('gestion_personal', False):
        menu_options["👥 Gestión Personal"] = "Alta/baja/editar trabajadores"
    if permisos.get('gestion_invernaderos', False):
        menu_options["🏭 Gestión Invernaderos"] = "Administrar invernaderos"
    if permisos.get('catalogos', False):
        menu_options["📚 Catálogos"] = "Departamentos, puestos, etc."
    if permisos.get('generar_qr', False):
        menu_options["📱 Generar QR"] = "Códigos QR para trabajadores"
    if permisos.get('cierre_dia', False) or permisos.get('auditoria_diaria', False):
        menu_options["🔒 Cierre de Día"] = "Auditoría y cierre diario"
    if st.session_state.get('user_rol') == 'admin' or permisos.get('gestion_usuarios', False):
        menu_options["👥 Gestión Usuarios"] = "Administrar usuarios y permisos"
    
    for option, desc in menu_options.items():
        if st.sidebar.button(option, use_container_width=True, help=desc, key=f"menu_{option.replace(' ', '_')}"):
            st.session_state.menu = option
            st.rerun()
    
    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Cerrar Sesión", use_container_width=True):
        logout_user()

# ==========================================
# FUNCIÓN PRINCIPAL
# ==========================================
def main():
    global supabase
    supabase = init_supabase()
    
    if supabase is None:
        st.error("❌ No se pudo conectar a Supabase. Verifica tu configuración.")
        st.stop()
    
    if 'menu' not in st.session_state:
        st.session_state.menu = "📊 Dashboard"
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    if not st.session_state.authenticated:
        show_login_page()
        return
    
    mostrar_menu_sidebar()
    
    # Navegación
    if st.session_state.menu == "📊 Dashboard":
        mostrar_dashboard_general()
    elif st.session_state.menu == "🌾 Registro Cosecha":
        st.header("🌾 Registro de Cosecha")
        tab1, tab2 = st.tabs(["📷 Escanear QR", "📝 Registrar Manual"])
        with tab1:
            escanear_qr_con_camara(tipo_evento="cosecha", mostrar_invernadero=True)
        with tab2:
            if not get_configuracion_sistema('registro_manual_cosecha'):
                st.warning("⚠️ El registro manual de cosecha está deshabilitado por el administrador")
            else:
                st.info("Registro manual de cosecha - Selecciona los datos manualmente")
                # Formulario manual simplificado
                trabajadores = get_all_workers()
                if not trabajadores.empty:
                    trabajador_id = st.selectbox("Trabajador", trabajadores.apply(lambda x: f"{x['id']} - {x['nombre']} {x['apellido_paterno']}", axis=1))
                    trabajador_id_int = int(trabajador_id.split(' - ')[0]) if trabajador_id else None
                    
                    invernaderos = get_invernaderos()
                    invernadero_id = invernaderos[0][0] if invernaderos else None
                    
                    cantidad_clams = st.number_input("Cantidad de Clams", min_value=0.0, step=1.0)
                    merma_kilos = st.number_input("Merma (kilos)", min_value=0.0, step=0.5)
                    
                    if st.button("Guardar Cosecha"):
                        if trabajador_id_int and cantidad_clams > 0:
                            data = {
                                'fecha': get_mexico_date(), 'dia': get_mexico_day_spanish(), 'semana': get_mexico_week(),
                                'trabajador_id': trabajador_id_int, 'invernadero_id': invernadero_id,
                                'tipo_cosecha': 'Nacional', 'calidad': 'Salmon', 'presentacion': '6 oz',
                                'cantidad_clams': cantidad_clams, 'merma_kilos': merma_kilos
                            }
                            success, msg = guardar_cosecha(data)
                            if success:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
                        else:
                            st.error("Complete los datos")
    elif st.session_state.menu == "🕐 Control Asistencia":
        st.header("🕐 Control de Asistencia")
        tab1, tab2 = st.tabs(["📷 Escanear QR", "📝 Registrar Manual"])
        with tab1:
            escanear_qr_con_camara(tipo_evento="asistencia", mostrar_invernadero=True)
        with tab2:
            if not get_configuracion_sistema('registro_manual_asistencia'):
                st.warning("⚠️ El registro manual de asistencia está deshabilitado por el administrador")
            else:
                trabajadores = get_all_workers()
                if not trabajadores.empty:
                    trabajador_id = st.selectbox("Trabajador", trabajadores.apply(lambda x: f"{x['id']} - {x['nombre']} {x['apellido_paterno']}", axis=1))
                    trabajador_id_int = int(trabajador_id.split(' - ')[0]) if trabajador_id else None
                    
                    tipo_evento = st.selectbox("Tipo de Evento", 
                        ["entrada_invernadero", "salida_comer", "regreso_comida", "salida_invernadero"],
                        format_func=lambda x: {'entrada_invernadero': 'Entrada', 'salida_comer': 'Salida a Comer',
                                               'regreso_comida': 'Regreso de Comida', 'salida_invernadero': 'Salida'}[x])
                    
                    if st.button("Registrar Evento"):
                        if trabajador_id_int:
                            success, msg = registrar_evento_asistencia(trabajador_id_int, None, tipo_evento)
                            if success:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
    elif st.session_state.menu == "📊 Avance Cosecha":
        st.header("📊 Avance de Cosecha")
        
        invernaderos = get_invernaderos()
        if invernaderos:
            invernadero = st.selectbox("Invernadero", invernaderos, format_func=lambda x: f"{x[1]} - {x[2]}")
            invernadero_id = invernadero[0]
            invernadero_nombre = invernadero[1]
            
            lineas_totales = get_lineas_totales_por_invernadero(invernadero_id, invernadero_nombre)
            st.info(f"Total de líneas: {lineas_totales}")
            
            ultimo_avance = get_ultimo_avance_dia(invernadero_id)
            valor_inicial = ultimo_avance['lineas_cosechadas'] if ultimo_avance else 0
            
            lineas_cosechadas = st.number_input("Líneas cosechadas", min_value=0, max_value=lineas_totales, value=valor_inicial)
            supervisor = st.text_input("Supervisor")
            turno = st.selectbox("Turno", REPORTE_TURNOS)
            
            if st.button("Registrar Avance"):
                if supervisor:
                    success, msg = registrar_avance_cosecha(invernadero_id, invernadero_nombre, lineas_cosechadas, supervisor, "", turno)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
                else:
                    st.error("Ingrese el nombre del supervisor")
    elif st.session_state.menu == "❄️ Traslado a Cámara Fría":
        st.header("❄️ Traslado a Cámara Fría")
        
        invernaderos = get_invernaderos()
        if invernaderos:
            invernadero = st.selectbox("Invernadero de origen", invernaderos, format_func=lambda x: f"{x[1]} - {x[2]}")
            invernadero_id = invernadero[0]
            
            detalle = get_detalle_cajas_por_invernadero_presentacion(invernadero_id)
            st.info(f"Cajas disponibles: 6 oz: {detalle['6 oz']:.0f} | 12 oz: {detalle['12 oz']:.0f}")
            
            trabajadores = get_all_workers()
            supervisores = trabajadores[trabajadores['puesto'].str.contains('Supervisor', case=False, na=False)] if not trabajadores.empty else trabajadores
            supervisor_id = st.selectbox("Supervisor que entrega", supervisores.apply(lambda x: x['id'], axis=1) if not supervisores.empty else [])
            
            recolectores = get_recolectores()
            recolector_id = st.selectbox("Recolector", [r[0] for r in recolectores]) if recolectores else None
            
            presentacion = st.selectbox("Presentación", ["6 oz", "12 oz"])
            cantidad_cajas = st.number_input("Cantidad de cajas", min_value=0.0, step=1.0)
            
            if st.button("Registrar Traslado"):
                if invernadero_id and supervisor_id and recolector_id and cantidad_cajas > 0:
                    success, msg = registrar_traslado_camara_fria(invernadero_id, cantidad_cajas, supervisor_id, recolector_id, "Nacional", presentacion, "", "")
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
    elif st.session_state.menu == "🗑️ Gestión Merma":
        st.header("🗑️ Gestión de Merma")
        
        invernaderos = get_invernaderos()
        if invernaderos:
            invernadero = st.selectbox("Invernadero", invernaderos, format_func=lambda x: f"{x[1]} - {x[2]}")
            invernadero_id = invernadero[0]
            
            supervisor = st.text_input("Supervisor")
            kilos_merma = st.number_input("Kilos de merma", min_value=0.0, step=0.5)
            tipo_merma = st.selectbox("Tipo de merma", ["Seleccionar...", "Fruta dañada", "Fruta sobremadura", "Fruta con defectos", "Otra"])
            registrado_por = st.text_input("Registrado por")
            
            if st.button("Registrar Merma"):
                if invernadero_id and supervisor and kilos_merma > 0 and tipo_merma != "Seleccionar..." and registrado_por:
                    success, msg = registrar_merma(invernadero_id, supervisor, kilos_merma, tipo_merma, "", registrado_por)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
    elif st.session_state.menu == "📦 Cajas en Mesa":
        st.header("📦 Cajas en Mesa")
        
        invernaderos = get_invernaderos()
        if invernaderos:
            invernadero = st.selectbox("Invernadero", invernaderos, format_func=lambda x: f"{x[1]} - {x[2]}")
            invernadero_id = invernadero[0]
            
            trabajadores = get_all_workers()
            trabajador_id = st.selectbox("Trabajador", trabajadores.apply(lambda x: x['id'], axis=1) if not trabajadores.empty else [])
            
            presentacion = st.selectbox("Presentación", ["6 oz", "12 oz"])
            cantidad_cajas = st.number_input("Cantidad de cajas", min_value=0.0, step=1.0)
            solicitando_apoyo = st.checkbox("Solicitar apoyo")
            
            if st.button("Registrar"):
                if invernadero_id and trabajador_id and cantidad_cajas > 0:
                    success, msg = registrar_cajas_mesa(invernadero_id, trabajador_id, cantidad_cajas, presentacion, solicitando_apoyo, "")
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
    elif st.session_state.menu == "📈 Proyecciones":
        st.header("📈 Proyecciones")
        
        semana = st.number_input("Semana", min_value=1, max_value=52, value=get_mexico_week())
        cajas_proyectadas = st.number_input("Cajas proyectadas", min_value=0.0, step=50.0)
        registrado_por = st.text_input("Registrado por")
        
        if st.button("Registrar Proyección"):
            if registrado_por and cajas_proyectadas > 0:
                success, msg = registrar_proyeccion(semana, cajas_proyectadas, registrado_por, "")
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
        
        st.subheader("Comparativa Real vs Proyectado")
        df_comparativa = get_comparativa_proyeccion_real_con_filtros(1, get_mexico_week())
        if not df_comparativa.empty:
            st.dataframe(df_comparativa, use_container_width=True)
    elif st.session_state.menu == "📋 Reportes":
        st.header("📋 Reportes")
        
        reporte_tipo = st.selectbox("Tipo de Reporte", ["Cosechas", "Traslados", "Merma", "Incidencias"])
        
        fecha_inicio = st.date_input("Fecha inicio", get_mexico_date() - timedelta(days=30))
        fecha_fin = st.date_input("Fecha fin", get_mexico_date())
        
        if reporte_tipo == "Cosechas":
            df = get_cosechas(fecha_inicio, fecha_fin)
        elif reporte_tipo == "Traslados":
            df = get_traslados_camara_fria(fecha_inicio, fecha_fin)
        elif reporte_tipo == "Merma":
            df = get_merma(fecha_inicio, fecha_fin)
        else:
            df = get_incidencias(fecha_inicio, fecha_fin)
        
        if not df.empty:
            st.dataframe(df, use_container_width=True)
            output = export_to_excel(df, reporte_tipo)
            st.download_button("📥 Exportar a Excel", data=output, file_name=f"{reporte_tipo}_{get_mexico_date()}.xlsx")
    elif st.session_state.menu == "👥 Gestión Personal":
        if st.session_state.get('user_rol') != 'admin':
            st.error("❌ No tienes permisos para acceder a esta sección.")
        else:
            mostrar_gestion_personal()
    elif st.session_state.menu == "🏭 Gestión Invernaderos":
        if st.session_state.get('user_rol') != 'admin':
            st.error("❌ No tienes permisos para acceder a esta sección.")
        else:
            st.header("🏭 Gestión de Invernaderos")
            
            with st.form("nuevo_invernadero"):
                nombre = st.text_input("Nombre del Invernadero")
                ubicacion = st.text_input("Ubicación")
                if st.form_submit_button("Agregar Invernadero"):
                    if nombre and ubicacion:
                        success, msg = add_invernadero(nombre, ubicacion)
                        if success:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
            
            invernaderos = get_all_invernaderos()
            if invernaderos:
                st.subheader("Lista de Invernaderos")
                for inv in invernaderos:
                    st.write(f"**{inv[1]}** - {inv[2]} (Líneas: {inv[3]})")
    elif st.session_state.menu == "📚 Catálogos":
        if st.session_state.get('user_rol') != 'admin':
            st.error("❌ No tienes permisos para acceder a esta sección.")
        else:
            st.header("📚 Catálogos")
            
            tab_deptos, tab_puestos = st.tabs(["Departamentos", "Puestos"])
            
            with tab_deptos:
                with st.form("nuevo_departamento"):
                    nuevo_depto = st.text_input("Nuevo Departamento")
                    if st.form_submit_button("Agregar"):
                        if nuevo_depto:
                            success, msg = add_catalog_item("departamentos", nuevo_depto)
                            if success:
                                st.success(msg)
                                st.rerun()
                deptos = get_departamentos()
                for d in deptos:
                    st.write(f"- {d[1]}")
            
            with tab_puestos:
                with st.form("nuevo_puesto"):
                    nuevo_puesto = st.text_input("Nuevo Puesto")
                    if st.form_submit_button("Agregar"):
                        if nuevo_puesto:
                            success, msg = add_catalog_item("puestos", nuevo_puesto)
                            if success:
                                st.success(msg)
                                st.rerun()
                puestos = get_puestos()
                for p in puestos:
                    st.write(f"- {p[1]}")
    elif st.session_state.menu == "📱 Generar QR":
        if st.session_state.get('user_rol') != 'admin':
            st.error("❌ No tienes permisos para acceder a esta sección.")
        else:
            st.header("📱 Generar Códigos QR")
            
            trabajadores = get_all_workers()
            if not trabajadores.empty:
                trabajador_seleccionado = st.selectbox("Seleccionar trabajador", 
                    trabajadores.apply(lambda x: f"{x['id']} - {x['nombre']} {x['apellido_paterno']}", axis=1))
                
                if trabajador_seleccionado:
                    id_trabajador = trabajador_seleccionado.split(' - ')[0]
                    nombre_completo = trabajador_seleccionado.split(' - ')[1]
                    
                    qr_bytes = generar_qr_trabajador_simple(id_trabajador, nombre_completo, "https://tu-app.streamlit.app")
                    st.image(qr_bytes, width=200)
                    st.download_button("📥 Descargar QR", data=qr_bytes, file_name=f"QR_{id_trabajador}.png", mime="image/png")
    elif st.session_state.menu == "🔒 Cierre de Día":
        st.header("🔒 Cierre de Día")
        
        fecha_cierre = st.date_input("Fecha a cerrar", get_mexico_date())
        
        if st.button("Generar Reporte de Cierre"):
            reporte = generar_reporte_auditoria_dia(fecha_cierre)
            if reporte:
                st.json(reporte)
                
                if st.button("Confirmar Cierre"):
                    success, msg = registrar_cierre_dia(fecha_cierre, st.session_state.get('user_nombre', 'Sistema'))
                    if success:
                        st.success(msg)
                        st.balloons()
                    else:
                        st.error(msg)
    elif st.session_state.menu == "👥 Gestión Usuarios":
        mostrar_gestion_usuarios()

if __name__ == "__main__":
    main()
