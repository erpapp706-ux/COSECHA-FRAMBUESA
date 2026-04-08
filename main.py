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
import av
from queue import Queue
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
    .kpi-value { font-size: 28px; font-weight: bold; }
    .kpi-label { font-size: 12px; opacity: 0.9; margin-top: 5px; }
    .section-title { font-size: 24px; font-weight: bold; color: #1e3c2c; margin: 20px 0 15px 0; border-left: 4px solid #2a6b3c; padding-left: 15px; }
    .date-card { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 12px; padding: 12px; text-align: center; }
    .time-card { background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); border-radius: 12px; padding: 12px; text-align: center; }
    .week-card { background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%); border-radius: 12px; padding: 12px; text-align: center; }
    .login-container { max-width: 400px; margin: 100px auto; padding: 30px; background: white; border-radius: 15px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }
    </style>
""", unsafe_allow_html=True)

REPORTE_TURNOS = ["Reporte 10:00am", "Reporte 12:00pm", "Reporte 02:00pm", "Reporte 03:00pm", "Reporte 04:00pm", "Reporte 05:00pm", "Reporte 06:00pm", "Reporte 07:00pm", "Reporte 08:00pm"]

# ==========================================
# FUNCIONES DE AUTENTICACIÓN
# ==========================================
def get_configuracion_sistema(clave):
    try:
        result = supabase.table('configuracion_sistema').select('valor').eq('clave', clave).execute()
        if result.data:
            return result.data[0]['valor'] == 'true'
    except:
        pass
    return True

def register_user(email, password, nombre, rol='supervisor', permisos=None, invernaderos_asignados=None):
    try:
        email = email.strip().lower()
        response = supabase.auth.sign_up({
            "email": email,
            "password": password,
            "options": {"data": {"nombre": nombre}, "email_confirm": True}
        })
        if response.user:
            user_id = response.user.id
            permisos_default = {
                "registro_cosecha": True, "dashboard": True, "proyecciones": True, "control_asistencia": True,
                "avance_cosecha": True, "traslado_camara_fria": True, "gestion_merma": True, "cajas_mesa": True,
                "registros_qr": True, "reportes": True, "gestion_invernaderos": False, "gestion_personal": False,
                "gestion_usuarios": False, "generar_qr": False, "catalogos": False, "cierre_dia": False
            }
            if permisos:
                permisos_default.update(permisos)
            supabase.table('perfiles_usuario').upsert({
                'id': user_id,
                'email': email,
                'nombre': nombre,
                'rol': rol,
                'permisos': permisos_default,
                'invernaderos_asignados': invernaderos_asignados or []
            }).execute()
            return {'success': True, 'message': f'✅ Usuario {nombre} creado exitosamente'}
        else:
            return {'success': False, 'error': 'No se pudo crear el usuario'}
    except Exception as e:
        error_msg = str(e)
        if "User already registered" in error_msg:
            return {'success': False, 'error': 'El email ya está registrado'}
        return {'success': False, 'error': f'Error: {error_msg}'}

def login_user(email, password):
    try:
        email = email.strip().lower()
        response = supabase.auth.sign_in_with_password({"email": email, "password": password})
        if response.user:
            user_id = response.user.id
            perfil = supabase.table('perfiles_usuario').select('*').eq('id', user_id).execute()
            if not perfil.data:
                permisos_default = {
                    "registro_cosecha": True, "dashboard": True, "proyecciones": True, "control_asistencia": True,
                    "avance_cosecha": True, "traslado_camara_fria": True, "gestion_merma": True, "cajas_mesa": True,
                    "registros_qr": True, "reportes": True, "gestion_invernaderos": False, "gestion_personal": False,
                    "gestion_usuarios": False, "generar_qr": False, "catalogos": False, "cierre_dia": False
                }
                nombre = response.user.user_metadata.get('nombre', email.split('@')[0])
                supabase.table('perfiles_usuario').insert({
                    'id': user_id,
                    'email': email,
                    'nombre': nombre,
                    'rol': 'supervisor',
                    'permisos': permisos_default,
                    'invernaderos_asignados': []
                }).execute()
                perfil = supabase.table('perfiles_usuario').select('*').eq('id', user_id).execute()
            rol = 'supervisor'
            nombre = email.split('@')[0]
            permisos = {}
            invernaderos_asignados = []
            if perfil.data and len(perfil.data) > 0:
                rol = perfil.data[0].get('rol', 'supervisor')
                nombre = perfil.data[0].get('nombre', nombre)
                permisos = perfil.data[0].get('permisos', {})
                invernaderos_asignados = perfil.data[0].get('invernaderos_asignados', [])
            return {
                'success': True,
                'user_id': user_id,
                'email': email,
                'rol': rol,
                'nombre': nombre,
                'permisos': permisos,
                'invernaderos_asignados': invernaderos_asignados
            }
    except Exception as e:
        return {'success': False, 'error': str(e)}
    return {'success': False, 'error': 'Error de autenticación'}

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
        supabase.table('perfiles_usuario').update({
            'rol': rol,
            'permisos': permisos,
            'invernaderos_asignados': invernaderos_asignados
        }).eq('id', user_id).execute()
        invalidar_cache()
        return True, "✅ Permisos actualizados correctamente"
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

def delete_user(user_id, email):
    try:
        supabase.table('asignaciones_invernaderos_dia').delete().eq('usuario_id', user_id).execute()
        supabase.table('perfiles_usuario').delete().eq('id', user_id).execute()
        invalidar_cache()
        return True, f"✅ Usuario {email} eliminado correctamente"
    except Exception as e:
        return False, f"❌ Error al eliminar: {str(e)}"

def reset_user_password(user_id, new_password):
    try:
        supabase.auth.admin.update_user_by_id(user_id, {"password": new_password})
        return True, "✅ Contraseña actualizada correctamente"
    except Exception as e:
        return False, f"❌ No se pudo cambiar la contraseña: {str(e)}"

# ==========================================
# FUNCIONES DE PERMISOS Y ASIGNACIONES
# ==========================================
def get_permisos_modulos(usuario_id):
    try:
        result = supabase.table('perfiles_usuario').select('permisos').eq('id', usuario_id).execute()
        if result.data:
            return result.data[0].get('permisos', {})
    except:
        pass
    return {}

def get_modulos_visibles(usuario_id):
    todos_modulos = {
        "registro_cosecha": "🌾 Registro Cosecha",
        "dashboard": "📊 Dashboard",
        "proyecciones": "📈 Proyecciones",
        "control_asistencia": "🕐 Control Asistencia",
        "avance_cosecha": "📊 Avance Cosecha",
        "traslado_camara_fria": "❄️ Traslado a Cámara Fría",
        "gestion_merma": "🗑️ Gestión Merma",
        "cajas_mesa": "📦 Cajas en Mesa",
        "registros_qr": "📊 Registros QR",
        "reportes": "📋 Reportes",
        "gestion_invernaderos": "🏭 Gestión Invernaderos",
        "gestion_personal": "👥 Gestión Personal",
        "gestion_usuarios": "👥 Gestión Usuarios",
        "generar_qr": "📱 Generar QR",
        "catalogos": "📚 Catálogos",
        "cierre_dia": "🔒 Cierre de Día"
    }
    if st.session_state.get('user_rol') == 'admin':
        return todos_modulos
    permisos = get_permisos_modulos(usuario_id)
    modulos_visibles = {}
    for key, name in todos_modulos.items():
        if permisos.get(key, False):
            modulos_visibles[key] = name
    return modulos_visibles

def get_invernaderos_asignados_dia(usuario_id, fecha=None):
    if not fecha:
        fecha = get_mexico_date()
    if st.session_state.get('user_rol') == 'admin':
        return get_all_invernaderos()
    try:
        result = supabase.table('asignaciones_invernaderos_dia').select('invernadero_id, invernaderos:invernadero_id(nombre, ubicacion, lineas_totales)').eq('usuario_id', usuario_id).eq('fecha', fecha.isoformat()).execute()
        if result.data:
            return [(row['invernadero_id'], row['invernaderos']['nombre'], row['invernaderos']['ubicacion'], row['invernaderos'].get('lineas_totales', 40)) for row in result.data]
        perfil = supabase.table('perfiles_usuario').select('invernaderos_asignados').eq('id', usuario_id).execute()
        if perfil.data and perfil.data[0].get('invernaderos_asignados'):
            invernaderos_ids = perfil.data[0]['invernaderos_asignados']
            if invernaderos_ids:
                result = supabase.table('invernaderos').select('id, nombre, ubicacion, lineas_totales').in_('id', invernaderos_ids).eq('activo', True).execute()
                return [(row['id'], row['nombre'], row['ubicacion'], row.get('lineas_totales', 40)) for row in result.data] if result.data else []
        return []
    except:
        return []

def asignar_invernaderos_dia(usuario_id, invernaderos_ids, fecha, asignado_por):
    try:
        supabase.table('asignaciones_invernaderos_dia').delete().eq('usuario_id', usuario_id).eq('fecha', fecha.isoformat()).execute()
        for inv_id in invernaderos_ids:
            supabase.table('asignaciones_invernaderos_dia').insert({
                'usuario_id': usuario_id,
                'invernadero_id': inv_id,
                'fecha': fecha.isoformat(),
                'asignado_por': asignado_por
            }).execute()
        invalidar_cache()
        return True, f"✅ Asignación actualizada para {fecha}"
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

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

def get_mexico_week():
    return get_mexico_date().isocalendar()[1]

def get_mexico_day_spanish():
    dias = {'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miércoles', 'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'Sábado', 'Sunday': 'Domingo'}
    return dias[get_mexico_date().strftime('%A')]

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
# FUNCIONES PARA CATÁLOGOS (RESUMIDAS)
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

def get_invernaderos_usuario():
    usuario_id = st.session_state.get('user_id')
    fecha_actual = get_mexico_date()
    return get_invernaderos_asignados_dia(usuario_id, fecha_actual)

def get_invernaderos():
    return get_all_invernaderos()

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
# FUNCIONES DE TRABAJADORES (RESUMIDAS)
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
# FUNCIONES PARA INVERNADEROS (RESUMIDAS)
# ==========================================
def add_invernadero(nombre, ubicacion, lineas_totales=40):
    try:
        supabase.table('invernaderos').insert({'nombre': nombre.strip().upper(), 'ubicacion': ubicacion, 'lineas_totales': lineas_totales, 'activo': True}).execute()
        invalidar_cache()
        return True, "✅ Invernadero agregado correctamente"
    except Exception as e:
        if 'duplicate key' in str(e).lower():
            return False, "❌ Este invernadero ya existe"
        return False, f"❌ Error: {str(e)}"

def update_invernadero(invernadero_id, nombre, ubicacion, lineas_totales):
    try:
        supabase.table('invernaderos').update({'nombre': nombre.strip().upper(), 'ubicacion': ubicacion, 'lineas_totales': lineas_totales}).eq('id', invernadero_id).execute()
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
# FUNCIONES DE AVANCE DE COSECHA (RESUMIDAS)
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
            return {'lineas_cosechadas': row['lineas_cosechadas'], 'porcentaje': row['porcentaje'], 'hora': row['hora'], 'turno': row['turno'], 'es_acumulado': row['es_acumulado']}
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
        invernaderos = get_all_invernaderos()
        inv_con_datos = set([d['invernadero_id'] for d in data])
        for inv_id, inv_nombre, inv_ubic, lineas in invernaderos:
            if inv_id not in inv_con_datos:
                data.append({
                    'id': None, 'invernadero_id': inv_id, 'fecha': fecha_hoy, 'hora': None, 'turno': None,
                    'semana': get_mexico_week(), 'lineas_cosechadas': 0, 'lineas_totales': lineas,
                    'porcentaje': 0.0, 'supervisor': None, 'observaciones': None, 'es_acumulado': 0, 'invernadero_nombre': inv_nombre
                })
        return pd.DataFrame(data)
    except Exception as e:
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
# FUNCIONES DE COSECHA (RESUMIDAS)
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
# FUNCIONES DE TRASLADOS Y PESAJE (RESUMIDAS)
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
            *, invernaderos:invernadero_id (nombre), trabajadores:trabajador_id (nombre, apellido_paterno),
            traslados_camara_fria:traslado_id (cantidad_cajas, presentacion)
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
                'presentacion': row['presentacion'], 'cajas_enviadas': row['traslados_camara_fria']['cantidad_cajas'] if row['traslados_camara_fria'] else 0,
                'cajas_pesadas': row['cantidad_cajas_pesadas'], 'cajas_recibidas': row['cajas_recibidas'],
                'diferencia': row['diferencia'], 'nota': row.get('nota', '')
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
# FUNCIONES DE CONTROL DE ASISTENCIA (RESUMIDAS)
# ==========================================
def registrar_evento_asistencia(trabajador_id, invernadero_id, tipo_evento):
    # Versión simplificada para que el código funcione
    try:
        fecha_actual = get_mexico_date()
        hora_actual = get_mexico_time().strftime("%H:%M:%S")
        if tipo_evento == 'entrada_invernadero':
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
            if registro_activo.data:
                reg = registro_activo.data[0]
                supabase.table('asistencia').update({'hora_salida': hora_actual, 'estado': 'finalizado', 'tipo_movimiento': tipo_evento}).eq('id', reg['id']).execute()
                supabase.table('registros_asistencia').insert({
                    'trabajador_id': trabajador_id, 'invernadero_id': reg.get('invernadero_id'), 'fecha': fecha_actual.isoformat(),
                    'hora': hora_actual, 'tipo_evento': tipo_evento
                }).execute()
            else:
                return False, "No hay registro de entrada activo"
        else:
            return False, "Tipo de evento no implementado en esta versión"
        invalidar_cache()
        return True, "✅ Evento registrado correctamente"
    except Exception as e:
        return False, f"❌ Error al registrar: {str(e)}"

def get_estado_asistencia_actual(trabajador_id):
    # Implementación básica
    return None

def get_registros_asistencia(filtros=None):
    return pd.DataFrame()

def get_resumen_asistencia_dia(fecha=None):
    return pd.DataFrame()

# ==========================================
# FUNCIONES DE MERMA, PROYECCIONES, ETC. (SIMPLIFICADAS)
# ==========================================
def registrar_merma(invernadero_id, supervisor_nombre, kilos_merma, tipo_merma, observaciones, registrado_por):
    try:
        supabase.table('merma').insert({
            'fecha': get_mexico_date().isoformat(), 'hora': get_mexico_time().strftime("%H:%M:%S"),
            'semana': get_mexico_week(), 'invernadero_id': invernadero_id, 'supervisor_nombre': supervisor_nombre,
            'kilos_merma': kilos_merma, 'tipo_merma': tipo_merma, 'observaciones': observaciones,
            'registrado_por': registrado_por
        }).execute()
        invalidar_cache()
        return True, "✅ Merma registrada"
    except Exception as e:
        return False, f"Error: {str(e)}"

def get_merma(fecha_inicio=None, fecha_fin=None, invernadero_id=None):
    return pd.DataFrame()

def get_stats_merma(fecha_inicio=None, fecha_fin=None):
    return {'total_merma': 0}

def registrar_proyeccion(semana, cajas_proyectadas, registrado_por, observaciones=""):
    try:
        supabase.table('proyecciones_cajas').upsert({'semana': semana, 'cajas_proyectadas': cajas_proyectadas, 'registrado_por': registrado_por, 'observaciones': observaciones}).execute()
        invalidar_cache()
        return True, f"✅ Proyección registrada para semana {semana}"
    except Exception as e:
        return False, f"Error: {str(e)}"

def get_proyecciones(semana=None):
    return pd.DataFrame()

def get_comparativa_proyeccion_real_con_filtros(semana_inicio=None, semana_fin=None, tipo_cosecha=None, presentacion=None):
    return pd.DataFrame()

def get_resumen_proyecciones_total_con_filtros_dashboard(df_cosechas):
    return {'total_proyectado': 0, 'total_real': 0, 'diferencia': 0, 'porcentaje_desviacion': 0}

def get_dashboard_stats():
    return {'total_activos': 0, 'total_bajas': 0, 'ingresos_mes': 0, 'df_deptos': pd.DataFrame(), 'df_nomina': pd.DataFrame()}

def get_report_ingresos_semana():
    return pd.DataFrame(), None, None

def get_report_bajas_semana():
    return pd.DataFrame(), None, None

def get_report_nomina_activa(depto_nombre=None, subdepto_nombre=None):
    return pd.DataFrame(), pd.DataFrame()

def mostrar_dashboard_general():
    st.info("Dashboard en construcción")

def mostrar_control_asistencia():
    st.info("Módulo de asistencia en construcción")

def mostrar_avance_cosecha():
    st.info("Módulo de avance de cosecha en construcción")

def mostrar_traslados_camara_fria():
    st.info("Módulo de traslados en construcción")

def mostrar_gestion_merma():
    st.info("Módulo de merma en construcción")

def mostrar_gestion_invernaderos():
    st.info("Módulo de invernaderos en construcción")

def mostrar_generar_qr():
    st.info("Módulo de generación de QR en construcción")

def mostrar_reportes_qr():
    st.info("Reportes QR en construcción")

def mostrar_reportes():
    st.info("Reportes en construcción")

def mostrar_catalogos():
    st.info("Catálogos en construcción")

def mostrar_proyecciones():
    st.info("Proyecciones en construcción")

def mostrar_cierre_dia():
    st.info("Cierre de día en construcción")

def mostrar_cajas_mesa():
    st.info("Cajas en mesa en construcción")

def mostrar_gestion_personal():
    st.info("Gestión de personal en construcción")

def formulario_cosecha_manual():
    st.info("Formulario de cosecha manual en construcción")

def mostrar_menu_sidebar():
    st.sidebar.markdown('<div class="sidebar-title"><h2>🌾 Sistema Integral</h2><p>Gestión Agrícola</p></div>', unsafe_allow_html=True)
    if st.session_state.get('authenticated', False):
        st.sidebar.markdown(f'<div class="user-info">👤 <strong>{st.session_state.get("user_nombre", "Usuario")}</strong><br>📧 {st.session_state.get("user_email", "")}<br>🎭 Rol: <strong>{st.session_state.get("user_rol", "supervisor").upper()}</strong></div>', unsafe_allow_html=True)
    modulos_visibles = get_modulos_visibles(st.session_state.get('user_id'))
    for module_key, module_name in modulos_visibles.items():
        if st.sidebar.button(module_name, use_container_width=True, key=f"menu_{module_key}"):
            st.session_state.menu = module_name
            st.rerun()
    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Cerrar Sesión", use_container_width=True):
        logout_user()

def escanear_qr_con_camara(tipo_evento="asistencia", mostrar_invernadero=False):
    st.info("Escaneo QR pendiente de implementación")

def mostrar_formulario_cosecha_instant(id_trabajador, nombre, mostrar_invernadero):
    st.info("Formulario instantáneo de cosecha")

def mostrar_formulario_asistencia_instant(id_trabajador, nombre):
    st.info("Formulario instantáneo de asistencia")

# ==========================================
# INTERFAZ DE GESTIÓN DE USUARIOS (COMPLETA)
# ==========================================
def mostrar_gestion_usuarios():
    st.header("👥 Gestión de Usuarios y Permisos")
    
    if st.session_state.get('user_rol') != 'admin':
        st.error("❌ No tienes permiso para acceder a esta sección")
        return
    
    tab1, tab2, tab3 = st.tabs(["📋 Lista de Usuarios", "➕ Crear Usuario", "📅 Asignación por Día"])
    
    with tab1:
        st.subheader("Usuarios del Sistema")
        usuarios = get_all_users()
        if not usuarios.empty:
            for _, usuario in usuarios.iterrows():
                with st.expander(f"👤 {usuario.get('nombre', 'Sin nombre')} - {usuario['email']} ({usuario.get('rol', 'supervisor')})"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**ID:** {usuario['id'][:8]}...")
                        st.write(f"**Email:** {usuario['email']}")
                        st.write(f"**Nombre:** {usuario.get('nombre', 'No especificado')}")
                        st.write(f"**Rol:** {usuario.get('rol', 'supervisor')}")
                    with col2:
                        st.write(f"**Invernaderos asignados:** {len(usuario.get('invernaderos_asignados', []))}")
                        permisos = usuario.get('permisos', {})
                        modulos_activos = [k for k, v in permisos.items() if v]
                        st.write(f"**Módulos activos:** {len(modulos_activos)}")
                    
                    col_acc1, col_acc2, col_acc3 = st.columns(3)
                    with col_acc1:
                        if st.button("✏️ Editar", key=f"edit_{usuario['id']}"):
                            st.session_state[f'editing_{usuario["id"]}'] = True
                    with col_acc2:
                        if st.button("🔑 Resetear Password", key=f"reset_{usuario['id']}"):
                            st.session_state[f'reset_{usuario["id"]}'] = True
                    with col_acc3:
                        if usuario['email'] != st.session_state.get('user_email'):
                            if st.button("🗑️ Eliminar", key=f"delete_{usuario['id']}"):
                                st.session_state[f'delete_{usuario["id"]}'] = True
                    
                    if st.session_state.get(f'editing_{usuario["id"]}', False):
                        with st.form(key=f"form_edit_{usuario['id']}"):
                            nuevo_rol = st.selectbox("Rol", ["admin", "supervisor"], index=0 if usuario.get('rol') == 'admin' else 1)
                            invernaderos = get_all_invernaderos()
                            invernaderos_actuales = usuario.get('invernaderos_asignados', [])
                            invernaderos_seleccionados = st.multiselect("Invernaderos", [inv[1] for inv in invernaderos], default=[inv[1] for inv in invernaderos if inv[0] in invernaderos_actuales])
                            invernaderos_ids = [inv[0] for inv in invernaderos if inv[1] in invernaderos_seleccionados]
                            if st.form_submit_button("💾 Guardar"):
                                success, msg = update_user_permissions(usuario['id'], nuevo_rol, usuario.get('permisos', {}), invernaderos_ids)
                                if success:
                                    st.success(msg)
                                    del st.session_state[f'editing_{usuario["id"]}']
                                    st.rerun()
                                else:
                                    st.error(msg)
                    
                    if st.session_state.get(f'reset_{usuario["id"]}', False):
                        with st.form(key=f"form_reset_{usuario['id']}"):
                            new_pw = st.text_input("Nueva contraseña", type="password")
                            if st.form_submit_button("Actualizar contraseña"):
                                if new_pw and len(new_pw) >= 6:
                                    success, msg = reset_user_password(usuario['id'], new_pw)
                                    if success:
                                        st.success(msg)
                                        del st.session_state[f'reset_{usuario["id"]}']
                                        st.rerun()
                                    else:
                                        st.error(msg)
                                else:
                                    st.error("Mínimo 6 caracteres")
                    
                    if st.session_state.get(f'delete_{usuario["id"]}', False):
                        st.warning(f"¿Eliminar a {usuario['nombre']}?")
                        col_yes, col_no = st.columns(2)
                        with col_yes:
                            if st.button("✅ Sí", key=f"confirm_del_{usuario['id']}"):
                                success, msg = delete_user(usuario['id'], usuario['email'])
                                if success:
                                    st.success(msg)
                                    del st.session_state[f'delete_{usuario["id"]}']
                                    st.rerun()
                                else:
                                    st.error(msg)
                        with col_no:
                            if st.button("❌ No", key=f"cancel_del_{usuario['id']}"):
                                del st.session_state[f'delete_{usuario["id"]}']
                                st.rerun()
        else:
            st.info("No hay usuarios registrados")
    
    with tab2:
        st.subheader("➕ Crear Nuevo Usuario")
        with st.form("form_crear_usuario"):
            col1, col2 = st.columns(2)
            with col1:
                nuevo_email = st.text_input("Email *")
                nuevo_nombre = st.text_input("Nombre completo *")
                nuevo_password = st.text_input("Contraseña *", type="password")
            with col2:
                nuevo_rol = st.selectbox("Rol *", ["supervisor", "admin"])
                invernaderos = get_all_invernaderos()
                invernaderos_nuevo = st.multiselect("Invernaderos asignados", [inv[1] for inv in invernaderos])
                invernaderos_ids_nuevo = [inv[0] for inv in invernaderos if inv[1] in invernaderos_nuevo]
            if st.form_submit_button("✅ Crear Usuario"):
                if not nuevo_email or not nuevo_nombre or not nuevo_password:
                    st.error("Complete todos los campos")
                elif len(nuevo_password) < 6:
                    st.error("La contraseña debe tener al menos 6 caracteres")
                else:
                    result = register_user(nuevo_email, nuevo_password, nuevo_nombre, nuevo_rol, None, invernaderos_ids_nuevo)
                    if result['success']:
                        st.success(result['message'])
                        st.rerun()
                    else:
                        st.error(result['error'])
    
    with tab3:
        st.subheader("📅 Asignación de Invernaderos por Día")
        usuarios = get_all_users()
        supervisores = usuarios[usuarios['rol'] == 'supervisor'] if not usuarios.empty else pd.DataFrame()
        if not supervisores.empty:
            supervisor = st.selectbox("Supervisor", supervisores.apply(lambda x: f"{x['id']} - {x['nombre']}", axis=1))
            supervisor_id = supervisor.split(' - ')[0] if supervisor else None
            fecha = st.date_input("Fecha", get_mexico_date())
            if supervisor_id:
                invernaderos = get_all_invernaderos()
                seleccionados = st.multiselect("Invernaderos para este día", [inv[1] for inv in invernaderos])
                invernaderos_ids = [inv[0] for inv in invernaderos if inv[1] in seleccionados]
                if st.button("Asignar"):
                    success, msg = asignar_invernaderos_dia(supervisor_id, invernaderos_ids, fecha, st.session_state.get('user_id'))
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
        else:
            st.info("No hay supervisores registrados")

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
    
    if st.session_state.menu == "🌾 Registro Cosecha":
        st.header("🌾 Registro de Cosecha")
        tab1, tab2 = st.tabs(["📷 Escanear QR", "📝 Registrar Manual"])
        with tab1:
            escanear_qr_con_camara(tipo_evento="cosecha", mostrar_invernadero=True)
        with tab2:
            if not get_configuracion_sistema('registro_manual_cosecha'):
                st.warning("⚠️ El registro manual de cosecha está deshabilitado por el administrador")
            else:
                formulario_cosecha_manual()
        with st.expander("📋 Ver Cosechas Registradas"):
            cosechas = get_cosechas()
            if not cosechas.empty:
                st.dataframe(cosechas, use_container_width=True)
                output = export_to_excel(cosechas, "Cosechas")
                st.download_button("📥 Exportar a Excel", data=output, file_name=f"cosechas_{get_mexico_date()}.xlsx")
            else:
                st.info("No hay cosechas registradas")
    elif st.session_state.menu == "👥 Gestión Personal":
        if st.session_state.get('user_rol') != 'admin':
            st.error("❌ No tienes permisos para acceder a esta sección.")
        else:
            mostrar_gestion_personal()
    elif st.session_state.menu == "📊 Dashboard":
        mostrar_dashboard_general()
    elif st.session_state.menu == "📈 Proyecciones":
        mostrar_proyecciones()
    elif st.session_state.menu == "🕐 Control Asistencia":
        mostrar_control_asistencia()
    elif st.session_state.menu == "📊 Avance Cosecha":
        mostrar_avance_cosecha()
    elif st.session_state.menu == "❄️ Traslado a Cámara Fría":
        mostrar_traslados_camara_fria()
    elif st.session_state.menu == "🗑️ Gestión Merma":
        mostrar_gestion_merma()
    elif st.session_state.menu == "📦 Cajas en Mesa":
        mostrar_cajas_mesa()
    elif st.session_state.menu == "📱 Generar QR":
        if st.session_state.get('user_rol') != 'admin':
            st.error("❌ No tienes permisos para acceder a esta sección.")
        else:
            mostrar_generar_qr()
    elif st.session_state.menu == "📊 Registros QR":
        mostrar_reportes_qr()
    elif st.session_state.menu == "📋 Reportes":
        mostrar_reportes()
    elif st.session_state.menu == "📚 Catálogos":
        if st.session_state.get('user_rol') != 'admin':
            st.error("❌ No tienes permisos para acceder a esta sección.")
        else:
            mostrar_catalogos()
    elif st.session_state.menu == "🏭 Gestión Invernaderos":
        mostrar_gestion_invernaderos()
    elif st.session_state.menu == "👥 Gestión Usuarios":
        if st.session_state.get('user_rol') != 'admin':
            st.error("❌ No tienes permisos para acceder a esta sección.")
        else:
            mostrar_gestion_usuarios()
    elif st.session_state.menu == "🔒 Cierre de Día":
        mostrar_cierre_dia()

if __name__ == "__main__":
    main()
