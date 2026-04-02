


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
from reportlab.lib.utils import ImageReader
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import cv2
import numpy as np
from pyzbar.pyzbar import decode
import time
import io
import zipfile
from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions
import bcrypt
from functools import wraps
import asyncio

# ==========================================
# CONEXIÓN A SUPABASE
# ==========================================

@st.cache_resource
def init_supabase() -> Client:
    """Inicializa el cliente de Supabase"""
    try:
        # Para Streamlit Cloud - usar secrets
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except:
        # Para desarrollo local - usar variables de entorno
        try:
            url = os.getenv("SUPABASE_URL", "https://tu-proyecto.supabase.co")
            key = os.getenv("SUPABASE_KEY", "tu-anon-key")
            return create_client(url, key)
        except Exception as e:
            st.error(f"❌ Error de conexión: {str(e)}")
            st.info("Configura tus credenciales en .streamlit/secrets.toml")
            return None

supabase = init_supabase()

def execute_query(table, operation="select", filters=None, data=None, order_by=None):
    """Ejecuta operaciones en Supabase"""
    if not supabase:
        return None if operation != "select" else pd.DataFrame()
    
    try:
        query = supabase.table(table)
        
        if operation == "select":
            if filters:
                for key, value in filters.items():
                    if isinstance(value, dict):
                        if value.get("operator") == "gte":
                            query = query.gte(key, value["value"])
                        elif value.get("operator") == "lte":
                            query = query.lte(key, value["value"])
                        elif value.get("operator") == "like":
                            query = query.like(key, value["value"])
                    else:
                        query = query.eq(key, value)
            
            if order_by:
                for field, direction in order_by.items():
                    query = query.order(field, desc=(direction == "desc"))
            
            response = query.execute()
            return pd.DataFrame(response.data) if response.data else pd.DataFrame()
        
        elif operation == "insert":
            response = query.insert(data).execute()
            return response.data
        
        elif operation == "update":
            if filters:
                for key, value in filters.items():
                    query = query.eq(key, value)
            response = query.update(data).execute()
            return response.data
        
        elif operation == "delete":
            if filters:
                for key, value in filters.items():
                    query = query.eq(key, value)
            response = query.delete().execute()
            return response.data
            
    except Exception as e:
        st.error(f"Error en operación {operation}: {str(e)}")
        return None if operation != "select" else pd.DataFrame()

def invalidar_cache():
    """Invalida la caché de Streamlit"""
    st.cache_data.clear()

# ==========================================
# CONFIGURACIÓN INICIAL DE STREAMLIT
# ==========================================

st.set_page_config(
    page_title="Sistema Integral de Gestión",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilo personalizado
st.markdown("""
    <style>
    .stButton > button {
        width: 100%;
        border-radius: 10px;
        padding: 12px;
        font-weight: bold;
        transition: all 0.3s;
        margin-bottom: 8px;
    }
    .stButton > button:hover {
        transform: translateX(5px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
    .sidebar-title {
        text-align: center;
        padding: 20px 0;
        border-bottom: 2px solid #e0e0e0;
        margin-bottom: 20px;
    }
    .sidebar-title h2 {
        color: #2c3e50;
        margin: 0;
    }
    .sidebar-title p {
        color: #7f8c8d;
        font-size: 12px;
        margin: 5px 0 0 0;
    }
    .success-message {
        padding: 10px;
        background-color: #d4edda;
        color: #155724;
        border-radius: 5px;
        border: 1px solid #c3e6cb;
    }
    .error-message {
        padding: 10px;
        background-color: #f8d7da;
        color: #721c24;
        border-radius: 5px;
        border: 1px solid #f5c6cb;
    }
    .info-card {
        background-color: #f8f9fa;
        padding: 20px;
        border-radius: 10px;
        border-left: 4px solid #667eea;
        margin: 10px 0;
    }
    .progress-card {
        background: linear-gradient(135deg, #1e3c2c 0%, #2a6b3c 100%);
        border-radius: 15px;
        padding: 20px;
        color: white;
        text-align: center;
    }
    .progress-value {
        font-size: 48px;
        font-weight: bold;
    }
    .date-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 12px;
        padding: 12px;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .time-card {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        border-radius: 12px;
        padding: 12px;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .week-card {
        background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);
        border-radius: 12px;
        padding: 12px;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .login-container {
        max-width: 400px;
        margin: 100px auto;
        padding: 30px;
        background: white;
        border-radius: 15px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
    }
    .user-info {
        padding: 10px;
        background: #f0f2f6;
        border-radius: 10px;
        margin-bottom: 20px;
        text-align: center;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# FUNCIONES DE AUTENTICACIÓN
# ==========================================

def init_auth_tables():
    """Inicializa las tablas de autenticación en Supabase si no existen"""
    try:
        # Verificar si existe la tabla perfiles_usuario
        result = supabase.table('perfiles_usuario').select('*').limit(1).execute()
    except Exception:
        # La tabla no existe, crear usando SQL directo (requiere service_role)
        try:
            sql = """
            CREATE TABLE IF NOT EXISTS perfiles_usuario (
                id UUID PRIMARY KEY,
                email TEXT NOT NULL,
                nombre TEXT,
                rol TEXT NOT NULL DEFAULT 'supervisor',
                activo BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
            """
            supabase.postgrest.rpc('exec_sql', {'sql': sql}).execute()
        except Exception:
            pass

def login_user(email, password):
    """Autentica un usuario con Supabase Auth"""
    try:
        # Intentar login con Supabase Auth
        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        
        if response.user:
            # Obtener rol del perfil
            perfil = supabase.table('perfiles_usuario').select('*').eq('id', response.user.id).execute()
            
            rol = 'supervisor'
            nombre = email.split('@')[0]
            
            if perfil.data and len(perfil.data) > 0:
                rol = perfil.data[0].get('rol', 'supervisor')
                nombre = perfil.data[0].get('nombre', nombre)
            
            return {
                'success': True,
                'user_id': response.user.id,
                'email': email,
                'rol': rol,
                'nombre': nombre
            }
    except Exception as e:
        error_msg = str(e)
        if "Invalid login credentials" in error_msg:
            return {'success': False, 'error': 'Email o contraseña incorrectos'}
        return {'success': False, 'error': error_msg}
    
    return {'success': False, 'error': 'Error de autenticación'}

def register_user(email, password, nombre, rol='supervisor'):
    """Registra un nuevo usuario"""
    try:
        # Registrar en Supabase Auth
        response = supabase.auth.sign_up({
            "email": email,
            "password": password,
            "options": {
                "data": {
                    "nombre": nombre
                }
            }
        })
        
        if response.user:
            # Crear perfil
            supabase.table('perfiles_usuario').insert({
                'id': response.user.id,
                'email': email,
                'nombre': nombre,
                'rol': rol
            }).execute()
            
            return {'success': True, 'message': 'Usuario registrado exitosamente'}
    except Exception as e:
        return {'success': False, 'error': str(e)}
    
    return {'success': False, 'error': 'Error al registrar usuario'}

def logout_user():
    """Cierra la sesión del usuario"""
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    
    for key in ['user_id', 'user_email', 'user_rol', 'user_nombre', 'authenticated']:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()

def require_auth(func):
    """Decorador para requerir autenticación"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not st.session_state.get('authenticated', False):
            show_login_page()
            return None
        return func(*args, **kwargs)
    return wrapper

def require_admin(func):
    """Decorador para requerir rol de administrador"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not st.session_state.get('authenticated', False):
            show_login_page()
            return None
        if st.session_state.get('user_rol') != 'admin':
            st.error("❌ No tienes permisos para acceder a esta sección. Se requiere rol de Administrador.")
            return None
        return func(*args, **kwargs)
    return wrapper

def show_login_page():
    """Muestra la página de login"""
    st.markdown("""
    <div style="text-align: center; padding: 40px 0;">
        <h1>🌾 Sistema Integral de Gestión Agrícola</h1>
        <p>Acceda con sus credenciales</p>
    </div>
    """, unsafe_allow_html=True)
    
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
                
                if st.button("Registrarse", type="primary", use_container_width=True):
                    if reg_email and reg_password and reg_nombre:
                        if reg_password != reg_confirm:
                            st.error("Las contraseñas no coinciden")
                        elif len(reg_password) < 6:
                            st.error("La contraseña debe tener al menos 6 caracteres")
                        else:
                            rol = 'supervisor'  # Por defecto supervisor
                            result = register_user(reg_email, reg_password, reg_nombre, rol)
                            if result['success']:
                                st.success(result['message'])
                                st.info("Ahora puedes iniciar sesión")
                            else:
                                st.error(result['error'])
                    else:
                        st.error("Complete todos los campos")
            
            st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# FUNCIONES DE UTILIDAD PARA SUPABASE
# ==========================================

def invalidar_cache():
    """Limpia la caché de Streamlit"""
    st.cache_data.clear()

def run_query(query, params=None):
    """Ejecuta una consulta SQL en Supabase (usando RPC si está disponible)"""
    try:
        if params:
            result = supabase.rpc('exec_sql', {'query': query, 'params': params}).execute()
        else:
            result = supabase.rpc('exec_sql', {'query': query}).execute()
        return result
    except Exception:
        # Si RPC no está disponible, usar métodos alternativos
        return None

# ==========================================
# FUNCIONES DE VALIDACIÓN
# ==========================================

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
# FUNCIONES PARA CATÁLOGOS (SUPABASE)
# ==========================================

def get_departamentos():
    try:
        result = supabase.table('departamentos').select('id, nombre').order('nombre').execute()
        return [(row['id'], row['nombre']) for row in result.data]
    except Exception as e:
        st.error(f"Error al obtener departamentos: {str(e)}")
        return []

def get_subdepartamentos():
    try:
        result = supabase.table('subdepartamentos').select('id, nombre').order('nombre').execute()
        return [(row['id'], row['nombre']) for row in result.data]
    except Exception as e:
        st.error(f"Error al obtener subdepartamentos: {str(e)}")
        return []

def get_puestos():
    try:
        result = supabase.table('puestos').select('id, nombre').order('nombre').execute()
        return [(row['id'], row['nombre']) for row in result.data]
    except Exception as e:
        st.error(f"Error al obtener puestos: {str(e)}")
        return []

def get_departamentos_nombres():
    return [nombre for _, nombre in get_departamentos()]

def get_subdepartamentos_nombres():
    return [nombre for _, nombre in get_subdepartamentos()]

def get_puestos_nombres():
    return [nombre for _, nombre in get_puestos()]

def add_catalog_item(tabla, nombre):
    try:
        result = supabase.table(tabla).insert({'nombre': nombre.lower().strip()}).execute()
        invalidar_cache()
        return True, "✅ Item agregado correctamente"
    except Exception as e:
        if 'duplicate key' in str(e).lower():
            return False, "❌ Este nombre ya existe"
        return False, f"❌ Error: {str(e)}"

def update_catalog_item(tabla, item_id, nuevo_nombre):
    try:
        result = supabase.table(tabla).update({'nombre': nuevo_nombre.lower().strip()}).eq('id', item_id).execute()
        invalidar_cache()
        return True, "✅ Item actualizado correctamente"
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

def delete_catalog_item(tabla, item_id):
    try:
        # Verificar si está siendo usado
        if tabla == "departamentos":
            check = supabase.table('trabajadores').select('id', count='exact').eq('departamento_id', item_id).execute()
        elif tabla == "subdepartamentos":
            check = supabase.table('trabajadores').select('id', count='exact').eq('subdepartamento_id', item_id).execute()
        else:
            check = supabase.table('trabajadores').select('id', count='exact').eq('puesto_id', item_id).execute()
        
        if check.count and check.count > 0:
            return False, f"❌ No se puede eliminar: {check.count} trabajadores lo están usando"
        
        result = supabase.table(tabla).delete().eq('id', item_id).execute()
        invalidar_cache()
        return True, "✅ Item eliminado correctamente"
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

# ==========================================
# FUNCIONES DE TRABAJADORES (SUPABASE)
# ==========================================

def get_id_by_nombre(tabla, nombre):
    try:
        result = supabase.table(tabla).select('id').eq('nombre', nombre).execute()
        if result.data:
            return result.data[0]['id']
        return None
    except Exception:
        return None

def get_all_workers():
    try:
        result = supabase.table('trabajadores').select("""
            id, nombre, apellido_paterno, apellido_materno,
            correo, telefono, estatus, fecha_alta, fecha_baja,
            tipo_nomina,
            departamentos:departamento_id (nombre),
            subdepartamentos:subdepartamento_id (nombre),
            puestos:puesto_id (nombre)
        """).eq('estatus', 'activo').order('apellido_paterno').execute()
        
        data = []
        for row in result.data:
            data.append({
                'id': row['id'],
                'nombre': row['nombre'],
                'apellido_paterno': row['apellido_paterno'],
                'apellido_materno': row['apellido_materno'],
                'correo': row['correo'],
                'telefono': row['telefono'],
                'estatus': row['estatus'],
                'fecha_alta': row['fecha_alta'],
                'fecha_baja': row['fecha_baja'],
                'departamento': row['departamentos']['nombre'] if row['departamentos'] else 'Sin asignar',
                'subdepartamento': row['subdepartamentos']['nombre'] if row['subdepartamentos'] else 'Sin asignar',
                'puesto': row['puestos']['nombre'] if row['puestos'] else 'Sin asignar',
                'tipo_nomina': row['tipo_nomina']
            })
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error al obtener trabajadores: {str(e)}")
        return pd.DataFrame()

def get_worker_by_id(worker_id):
    try:
        result = supabase.table('trabajadores').select("""
            *,
            departamentos:departamento_id (nombre),
            subdepartamentos:subdepartamento_id (nombre),
            puestos:puesto_id (nombre)
        """).eq('id', worker_id).execute()
        
        if result.data:
            row = result.data[0]
            return {
                'id': row['id'],
                'nombre': row['nombre'],
                'apellido_paterno': row['apellido_paterno'],
                'apellido_materno': row['apellido_materno'],
                'correo': row['correo'],
                'telefono': row['telefono'],
                'estatus': row['estatus'],
                'fecha_alta': row['fecha_alta'],
                'fecha_baja': row['fecha_baja'],
                'departamento_id': row['departamento_id'],
                'subdepartamento_id': row['subdepartamento_id'],
                'puesto_id': row['puesto_id'],
                'tipo_nomina': row['tipo_nomina'],
                'departamento_nombre': row['departamentos']['nombre'] if row['departamentos'] else '',
                'subdepartamento_nombre': row['subdepartamentos']['nombre'] if row['subdepartamentos'] else '',
                'puesto_nombre': row['puestos']['nombre'] if row['puestos'] else ''
            }
        return None
    except Exception as e:
        st.error(f"Error al obtener trabajador: {str(e)}")
        return None

def add_worker(data):
    try:
        depto_id = get_id_by_nombre("departamentos", data['departamento'])
        sub_id = get_id_by_nombre("subdepartamentos", data['subdepartamento'])
        puesto_id = get_id_by_nombre("puestos", data['puesto'])
        
        result = supabase.table('trabajadores').insert({
            'apellido_paterno': data['ap'],
            'apellido_materno': data['am'],
            'nombre': data['nom'],
            'correo': data['cor'],
            'telefono': data['tel'],
            'fecha_alta': data['fa'],
            'estatus': 'activo',
            'departamento_id': depto_id,
            'subdepartamento_id': sub_id,
            'tipo_nomina': data['tn'],
            'puesto_id': puesto_id
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
        
        result = supabase.table('trabajadores').update({
            'apellido_paterno': data['apellido_paterno'],
            'apellido_materno': data['apellido_materno'],
            'nombre': data['nombre'],
            'correo': data['correo'],
            'telefono': data['telefono'],
            'departamento_id': depto_id,
            'subdepartamento_id': sub_id,
            'tipo_nomina': data['tipo_nomina'],
            'puesto_id': puesto_id,
            'estatus': data['estatus'],
            'updated_at': datetime.now().isoformat()
        }).eq('id', worker_id).execute()
        
        invalidar_cache()
        return True, "✅ Cambios guardados correctamente"
    except Exception as e:
        return False, f"❌ Error al actualizar: {str(e)}"

def dar_baja(worker_id, fecha_baja):
    try:
        result = supabase.table('trabajadores').update({
            'estatus': 'baja',
            'fecha_baja': fecha_baja,
            'updated_at': datetime.now().isoformat()
        }).eq('id', worker_id).execute()
        
        invalidar_cache()
        return True, f"✅ Trabajador dado de baja correctamente"
    except Exception as e:
        return False, f"❌ Error al dar de baja: {str(e)}"

def reactivar_trabajador(worker_id):
    try:
        result = supabase.table('trabajadores').update({
            'estatus': 'activo',
            'fecha_baja': None,
            'updated_at': datetime.now().isoformat()
        }).eq('id', worker_id).execute()
        
        invalidar_cache()
        return True, f"✅ Trabajador reactivado correctamente"
    except Exception as e:
        return False, f"❌ Error al reactivar: {str(e)}"

def search_workers(search_term, estatus_filter="todos"):
    try:
        query = supabase.table('trabajadores').select("""
            id, nombre, apellido_paterno, apellido_materno,
            correo, telefono, estatus, fecha_alta, fecha_baja,
            tipo_nomina,
            departamentos:departamento_id (nombre),
            subdepartamentos:subdepartamento_id (nombre),
            puestos:puesto_id (nombre)
        """)
        
        # Búsqueda por nombre o apellido
        if search_term:
            query = query.or_(f"nombre.ilike.%{search_term}%,apellido_paterno.ilike.%{search_term}%,apellido_materno.ilike.%{search_term}%")
        
        if estatus_filter != "todos":
            query = query.eq('estatus', estatus_filter)
        
        query = query.order('apellido_paterno')
        result = query.execute()
        
        data = []
        for row in result.data:
            data.append({
                'id': row['id'],
                'nombre': row['nombre'],
                'apellido_paterno': row['apellido_paterno'],
                'apellido_materno': row['apellido_materno'],
                'correo': row['correo'],
                'telefono': row['telefono'],
                'estatus': row['estatus'],
                'fecha_alta': row['fecha_alta'],
                'fecha_baja': row['fecha_baja'],
                'departamento': row['departamentos']['nombre'] if row['departamentos'] else 'Sin asignar',
                'subdepartamento': row['subdepartamentos']['nombre'] if row['subdepartamentos'] else 'Sin asignar',
                'puesto': row['puestos']['nombre'] if row['puestos'] else 'Sin asignar',
                'tipo_nomina': row['tipo_nomina']
            })
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error al buscar: {str(e)}")
        return pd.DataFrame()

# ==========================================
# FUNCIONES PARA INVERNADEROS (SUPABASE)
# ==========================================

def get_invernaderos():
    try:
        result = supabase.table('invernaderos').select('id, nombre, ubicacion').eq('activo', True).order('nombre').execute()
        return [(row['id'], row['nombre'], row['ubicacion']) for row in result.data]
    except Exception as e:
        st.error(f"Error al obtener invernaderos: {str(e)}")
        return []

def add_invernadero(nombre, ubicacion):
    try:
        result = supabase.table('invernaderos').insert({
            'nombre': nombre.strip().upper(),
            'ubicacion': ubicacion,
            'activo': True
        }).execute()
        invalidar_cache()
        return True, "✅ Invernadero agregado correctamente"
    except Exception as e:
        if 'duplicate key' in str(e).lower():
            return False, "❌ Este invernadero ya existe"
        return False, f"❌ Error: {str(e)}"

def update_invernadero(invernadero_id, nombre, ubicacion):
    try:
        result = supabase.table('invernaderos').update({
            'nombre': nombre.strip().upper(),
            'ubicacion': ubicacion
        }).eq('id', invernadero_id).execute()
        invalidar_cache()
        return True, "✅ Invernadero actualizado correctamente"
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

def delete_invernadero(invernadero_id):
    try:
        # Verificar si tiene registros asociados
        check = supabase.table('asistencia').select('id', count='exact').eq('invernadero_id', invernadero_id).execute()
        if check.count and check.count > 0:
            # Desactivar en lugar de eliminar
            result = supabase.table('invernaderos').update({'activo': False}).eq('id', invernadero_id).execute()
            invalidar_cache()
            return True, "✅ Invernadero desactivado correctamente"
        
        result = supabase.table('invernaderos').delete().eq('id', invernadero_id).execute()
        invalidar_cache()
        return True, "✅ Invernadero eliminado correctamente"
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

# ==========================================
# FUNCIONES DE AVANCE DE COSECHA (SUPABASE)
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
        fecha = datetime.now().date()
    
    try:
        result = supabase.table('avance_cosecha').select('lineas_cosechadas, porcentaje, hora, turno, es_acumulado')\
            .eq('invernadero_id', invernadero_id)\
            .eq('fecha', fecha.isoformat())\
            .order('created_at', desc=True)\
            .limit(1)\
            .execute()
        
        if result.data:
            row = result.data[0]
            return {
                'lineas_cosechadas': row['lineas_cosechadas'],
                'porcentaje': row['porcentaje'],
                'hora': row['hora'],
                'turno': row['turno'],
                'es_acumulado': row['es_acumulado']
            }
        return None
    except Exception as e:
        return None

def get_avance_hoy_por_invernadero():
    fecha_hoy = datetime.now().date().isoformat()
    
    try:
        # Obtener último avance por invernadero
        result = supabase.table('avance_cosecha').select("""
            *,
            invernaderos:invernadero_id (nombre)
        """).eq('fecha', fecha_hoy).execute()
        
        # Procesar para obtener último por invernadero
        ultimos = {}
        for row in result.data:
            inv_id = row['invernadero_id']
            if inv_id not in ultimos or row['created_at'] > ultimos[inv_id]['created_at']:
                ultimos[inv_id] = row
        
        data = []
        for inv_id, row in ultimos.items():
            data.append({
                'id': row['id'],
                'invernadero_id': inv_id,
                'fecha': row['fecha'],
                'hora': row['hora'],
                'turno': row['turno'],
                'semana': row['semana'],
                'lineas_cosechadas': row['lineas_cosechadas'],
                'lineas_totales': row['lineas_totales'],
                'porcentaje': row['porcentaje'],
                'supervisor': row['supervisor'],
                'observaciones': row['observaciones'],
                'es_acumulado': row['es_acumulado'],
                'invernadero_nombre': row['invernaderos']['nombre'] if row['invernaderos'] else 'Desconocido'
            })
        
        # Agregar invernaderos sin registros
        invernaderos = get_invernaderos()
        inv_con_datos = set([d['invernadero_id'] for d in data])
        
        for inv_id, inv_nombre, inv_ubic in invernaderos:
            if inv_id not in inv_con_datos:
                lineas_totales = get_lineas_totales_por_invernadero(inv_id, inv_nombre)
                data.append({
                    'id': None,
                    'invernadero_id': inv_id,
                    'fecha': fecha_hoy,
                    'hora': None,
                    'turno': None,
                    'semana': datetime.now().isocalendar()[1],
                    'lineas_cosechadas': 0,
                    'lineas_totales': lineas_totales,
                    'porcentaje': 0.0,
                    'supervisor': None,
                    'observaciones': None,
                    'es_acumulado': 0,
                    'invernadero_nombre': inv_nombre
                })
        
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error al obtener avance: {str(e)}")
        return pd.DataFrame()

def get_avance_historico_por_dia(fecha_inicio=None, fecha_fin=None, invernadero_id=None, turno=None):
    if not fecha_inicio:
        fecha_inicio = datetime.now().date() - timedelta(days=30)
    if not fecha_fin:
        fecha_fin = datetime.now().date()
    
    try:
        query = supabase.table('avance_cosecha').select("""
            *,
            invernaderos:invernadero_id (nombre)
        """)
        
        query = query.gte('fecha', fecha_inicio.isoformat())
        query = query.lte('fecha', fecha_fin.isoformat())
        
        if invernadero_id:
            query = query.eq('invernadero_id', invernadero_id)
        if turno:
            query = query.eq('turno', turno)
        
        result = query.order('fecha', desc=True).order('created_at', desc=True).execute()
        
        # Obtener último registro por día e invernadero
        ultimos = {}
        for row in result.data:
            key = f"{row['invernadero_id']}_{row['fecha']}"
            if key not in ultimos:
                ultimos[key] = row
        
        data = []
        for row in ultimos.values():
            data.append({
                'id': row['id'],
                'invernadero_id': row['invernadero_id'],
                'fecha': row['fecha'],
                'hora': row['hora'],
                'turno': row['turno'],
                'semana': row['semana'],
                'lineas_cosechadas': row['lineas_cosechadas'],
                'lineas_totales': row['lineas_totales'],
                'porcentaje': row['porcentaje'],
                'supervisor': row['supervisor'],
                'observaciones': row['observaciones'],
                'es_acumulado': row['es_acumulado'],
                'invernadero_nombre': row['invernaderos']['nombre'] if row['invernaderos'] else 'Desconocido'
            })
        
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error al obtener historial: {str(e)}")
        return pd.DataFrame()

def registrar_avance_cosecha(invernadero_id, invernadero_nombre, lineas_cosechadas, supervisor, observaciones, turno=None):
    try:
        fecha_actual = datetime.now().date()
        hora_actual = datetime.now().time().strftime("%H:%M:%S")
        semana_actual = fecha_actual.isocalendar()[1]
        lineas_totales = get_lineas_totales_por_invernadero(invernadero_id, invernadero_nombre)
        
        # Verificar registros hoy
        check = supabase.table('avance_cosecha').select('id', count='exact')\
            .eq('invernadero_id', invernadero_id)\
            .eq('fecha', fecha_actual.isoformat())\
            .execute()
        
        registros_hoy = check.count if check.count else 0
        
        if lineas_cosechadas > lineas_totales:
            return False, f"❌ Las líneas cosechadas ({lineas_cosechadas}) no pueden exceder el total ({lineas_totales})"
        
        if not turno:
            hora_int = int(hora_actual.split(':')[0])
            if 6 <= hora_int < 14:
                turno = "Matutino"
            elif 14 <= hora_int < 22:
                turno = "Vespertino"
            else:
                turno = "Nocturno"
        
        porcentaje = (lineas_cosechadas / lineas_totales) * 100
        
        result = supabase.table('avance_cosecha').insert({
            'invernadero_id': invernadero_id,
            'fecha': fecha_actual.isoformat(),
            'hora': hora_actual,
            'turno': turno,
            'semana': semana_actual,
            'lineas_cosechadas': lineas_cosechadas,
            'lineas_totales': lineas_totales,
            'porcentaje': porcentaje,
            'supervisor': supervisor,
            'observaciones': observaciones,
            'es_acumulado': False
        }).execute()
        
        invalidar_cache()
        
        if registros_hoy == 0:
            return True, f"✅ Primer avance del día registrado: {porcentaje:.1f}% completado (Turno: {turno})"
        else:
            return True, f"✅ Avance actualizado: {porcentaje:.1f}% completado (Turno: {turno})"
        
    except Exception as e:
        return False, f"❌ Error al registrar avance: {str(e)}"

def get_avance_cosecha(fecha=None, invernadero_id=None, turno=None):
    try:
        query = supabase.table('avance_cosecha').select("""
            *,
            invernaderos:invernadero_id (nombre)
        """)
        
        if fecha:
            query = query.eq('fecha', fecha.isoformat() if isinstance(fecha, date) else fecha)
        if invernadero_id:
            query = query.eq('invernadero_id', invernadero_id)
        if turno:
            query = query.eq('turno', turno)
        
        result = query.order('fecha', desc=True).order('created_at', desc=True).execute()
        
        data = []
        for row in result.data:
            data.append({
                'id': row['id'],
                'invernadero_id': row['invernadero_id'],
                'fecha': row['fecha'],
                'hora': row['hora'],
                'turno': row['turno'],
                'semana': row['semana'],
                'lineas_cosechadas': row['lineas_cosechadas'],
                'lineas_totales': row['lineas_totales'],
                'porcentaje': row['porcentaje'],
                'supervisor': row['supervisor'],
                'observaciones': row['observaciones'],
                'es_acumulado': row['es_acumulado'],
                'invernadero_nombre': row['invernaderos']['nombre'] if row['invernaderos'] else 'Desconocido'
            })
        
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error al obtener avance: {str(e)}")
        return pd.DataFrame()

# ==========================================
# FUNCIONES DE COSECHA Y ENVÍOS (SUPABASE)
# ==========================================

def guardar_cosecha(data):
    try:
        if data['presentacion'] == "12 oz":
            numero_cajas = data['cantidad_clams'] / 6
        else:
            numero_cajas = data['cantidad_clams'] / 12
        
        result = supabase.table('cosechas').insert({
            'fecha': data['fecha'].isoformat() if isinstance(data['fecha'], date) else data['fecha'],
            'dia': data['dia'],
            'semana': data['semana'],
            'trabajador_id': data['trabajador_id'],
            'invernadero_id': data['invernadero_id'],
            'tipo_cosecha': data['tipo_cosecha'],
            'calidad': data['calidad'],
            'presentacion': data['presentacion'],
            'cantidad_clams': data['cantidad_clams'],
            'numero_cajas': numero_cajas,
            'cajas_enviadas': 0
        }).execute()
        
        invalidar_cache()
        return True, f"✅ Cosecha registrada correctamente - {numero_cajas:.2f} cajas en invernadero"
    except Exception as e:
        return False, f"❌ Error al guardar: {str(e)}"

def get_cosechas(fecha_inicio=None, fecha_fin=None):
    try:
        query = supabase.table('cosechas').select("""
            *,
            trabajadores:trabajador_id (nombre, apellido_paterno),
            invernaderos:invernadero_id (nombre)
        """)
        
        if fecha_inicio:
            query = query.gte('fecha', fecha_inicio.isoformat() if isinstance(fecha_inicio, date) else fecha_inicio)
        if fecha_fin:
            query = query.lte('fecha', fecha_fin.isoformat() if isinstance(fecha_fin, date) else fecha_fin)
        
        result = query.order('fecha', desc=True).order('id', desc=True).execute()
        
        data = []
        for row in result.data:
            trabajador_nombre = ""
            if row['trabajadores']:
                trabajador_nombre = f"{row['trabajadores'].get('nombre', '')} {row['trabajadores'].get('apellido_paterno', '')}"
            
            data.append({
                'id': row['id'],
                'fecha': row['fecha'],
                'dia': row['dia'],
                'semana': row['semana'],
                'trabajador_id': row['trabajador_id'],
                'trabajador_nombre': trabajador_nombre,
                'invernadero_id': row['invernadero_id'],
                'invernadero_nombre': row['invernaderos']['nombre'] if row['invernaderos'] else 'Desconocido',
                'tipo_cosecha': row['tipo_cosecha'],
                'calidad': row['calidad'],
                'presentacion': row['presentacion'],
                'cantidad_clams': row['cantidad_clams'],
                'numero_cajas': row['numero_cajas'],
                'cajas_enviadas': row['cajas_enviadas'],
                'cajas_disponibles': row['numero_cajas'] - row['cajas_enviadas']
            })
        
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error al obtener cosechas: {str(e)}")
        return pd.DataFrame()

# ==========================================
# FUNCIONES PARA CAJAS DISPONIBLES (SUPABASE)
# ==========================================

def get_cajas_disponibles_por_invernadero(invernadero_id):
    try:
        result = supabase.table('cosechas').select('numero_cajas, cajas_enviadas')\
            .eq('invernadero_id', invernadero_id).execute()
        
        disponibles = 0
        for row in result.data:
            disponibles += (row['numero_cajas'] - row['cajas_enviadas'])
        return disponibles
    except Exception:
        return 0

def get_detalle_cajas_por_invernadero_presentacion(invernadero_id):
    try:
        result = supabase.table('cosechas').select('presentacion, numero_cajas, cajas_enviadas')\
            .eq('invernadero_id', invernadero_id).execute()
        
        resultados = {'6 oz': 0, '12 oz': 0}
        for row in result.data:
            presentacion = row['presentacion']
            disponibles = row['numero_cajas'] - row['cajas_enviadas']
            if presentacion in resultados:
                resultados[presentacion] += disponibles
        
        return resultados
    except Exception:
        return {'6 oz': 0, '12 oz': 0}

def get_detalle_cajas_por_invernadero(invernadero_id):
    try:
        # Obtener cosechas
        cosechas = supabase.table('cosechas').select('id, fecha, presentacion, cantidad_clams, numero_cajas, cajas_enviadas')\
            .eq('invernadero_id', invernadero_id)\
            .order('fecha', desc=True)\
            .order('id', desc=True)\
            .execute()
        
        cosechas_data = []
        for row in cosechas.data:
            cosechas_data.append({
                'id': row['id'],
                'fecha': row['fecha'],
                'presentacion': row['presentacion'],
                'cantidad_clams': row['cantidad_clams'],
                'numero_cajas': row['numero_cajas'],
                'cajas_enviadas': row['cajas_enviadas'],
                'disponibles': row['numero_cajas'] - row['cajas_enviadas']
            })
        
        # Obtener envíos
        envios = supabase.table('envios_enfriado').select("""
            id, fecha, hora, tipo_envio, presentacion, cantidad_cajas, lote, observaciones,
            trabajadores:trabajador_id (nombre, apellido_paterno)
        """)\
            .eq('invernadero_id', invernadero_id)\
            .order('fecha', desc=True)\
            .order('hora', desc=True)\
            .execute()
        
        envios_data = []
        for row in envios.data:
            supervisor = ""
            if row['trabajadores']:
                supervisor = f"{row['trabajadores'].get('nombre', '')} {row['trabajadores'].get('apellido_paterno', '')}"
            
            envios_data.append({
                'id': row['id'],
                'fecha': row['fecha'],
                'hora': row['hora'],
                'tipo_envio': row['tipo_envio'],
                'presentacion': row['presentacion'],
                'cantidad_cajas': row['cantidad_cajas'],
                'lote': row.get('lote', ''),
                'observaciones': row.get('observaciones', ''),
                'supervisor': supervisor
            })
        
        return pd.DataFrame(cosechas_data), pd.DataFrame(envios_data)
    except Exception as e:
        st.error(f"Error al obtener detalle: {str(e)}")
        return pd.DataFrame(), pd.DataFrame()

def get_resumen_cajas_por_invernadero():
    try:
        # Obtener todos los invernaderos activos
        invernaderos = get_invernaderos()
        
        resumen = []
        for inv_id, inv_nombre, _ in invernaderos:
            result = supabase.table('cosechas').select('numero_cajas, cajas_enviadas')\
                .eq('invernadero_id', inv_id).execute()
            
            cosechadas = 0
            enviadas = 0
            for row in result.data:
                cosechadas += row['numero_cajas']
                enviadas += row['cajas_enviadas']
            
            resumen.append({
                'id': inv_id,
                'invernadero': inv_nombre,
                'cosechadas': cosechadas,
                'enviadas': enviadas,
                'disponibles': cosechadas - enviadas
            })
        
        return pd.DataFrame(resumen)
    except Exception:
        return pd.DataFrame(columns=['id', 'invernadero', 'cosechadas', 'enviadas', 'disponibles'])

# ==========================================
# FUNCIONES DE ENVÍOS (SUPABASE)
# ==========================================

def registrar_envio_enfriado(invernadero_id, cantidad_cajas, trabajador_envia_id, tipo_envio, presentacion, lote, observaciones):
    try:
        fecha_actual = datetime.now().date()
        hora_actual = datetime.now().time().strftime("%H:%M:%S")
        semana_actual = fecha_actual.isocalendar()[1]
        
        # Registrar envío
        result = supabase.table('envios_enfriado').insert({
            'fecha': fecha_actual.isoformat(),
            'hora': hora_actual,
            'semana': semana_actual,
            'invernadero_id': invernadero_id,
            'trabajador_id': trabajador_envia_id,
            'tipo_envio': tipo_envio,
            'presentacion': presentacion,
            'cantidad_cajas': cantidad_cajas,
            'lote': lote if lote else None,
            'observaciones': observaciones if observaciones else None
        }).execute()
        
        # Actualizar cajas_enviadas en cosechas (más recientes primero)
        cosechas = supabase.table('cosechas').select('id, numero_cajas, cajas_enviadas')\
            .eq('invernadero_id', invernadero_id)\
            .eq('presentacion', presentacion)\
            .order('fecha', desc=True)\
            .order('id', desc=True)\
            .execute()
        
        cajas_restantes = cantidad_cajas
        for cosecha in cosechas.data:
            if cajas_restantes <= 0:
                break
            
            disponibles = cosecha['numero_cajas'] - cosecha['cajas_enviadas']
            if disponibles > 0:
                a_enviar = min(disponibles, cajas_restantes)
                nuevo_enviado = cosecha['cajas_enviadas'] + a_enviar
                
                supabase.table('cosechas').update({'cajas_enviadas': nuevo_enviado})\
                    .eq('id', cosecha['id']).execute()
                
                cajas_restantes -= a_enviar
        
        invalidar_cache()
        return True, f"✅ Envío registrado correctamente"
    except Exception as e:
        return False, f"❌ Error al registrar: {str(e)}"

def get_envios_enfriado(fecha_inicio=None, fecha_fin=None, invernadero_id=None):
    try:
        query = supabase.table('envios_enfriado').select("""
            *,
            invernaderos:invernadero_id (nombre),
            trabajadores:trabajador_id (nombre, apellido_paterno)
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
            trabajador_envia = ""
            if row['trabajadores']:
                trabajador_envia = f"{row['trabajadores'].get('nombre', '')} {row['trabajadores'].get('apellido_paterno', '')}"
            
            data.append({
                'id': row['id'],
                'fecha': row['fecha'],
                'hora': row['hora'],
                'semana': row['semana'],
                'invernadero_id': row['invernadero_id'],
                'invernadero': row['invernaderos']['nombre'] if row['invernaderos'] else 'Desconocido',
                'trabajador_id': row['trabajador_id'],
                'trabajador_envia': trabajador_envia,
                'tipo_envio': row['tipo_envio'],
                'presentacion': row['presentacion'],
                'cantidad_cajas': row['cantidad_cajas'],
                'lote': row.get('lote', ''),
                'observaciones': row.get('observaciones', '')
            })
        
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error al obtener envíos: {str(e)}")
        return pd.DataFrame()

def get_stats_envios_avanzado(fecha_inicio=None, fecha_fin=None):
    envios = get_envios_enfriado(fecha_inicio, fecha_fin)
    
    if envios.empty:
        return {
            'total_cajas': 0,
            'envios_por_invernadero': pd.DataFrame(),
            'envios_diarios': pd.DataFrame(),
            'top_trabajadores_envian': pd.DataFrame(),
            'resumen_presentacion': pd.DataFrame()
        }
    
    total_cajas = envios['cantidad_cajas'].sum() if 'cantidad_cajas' in envios.columns else 0
    
    envios_por_invernadero = envios.groupby(['invernadero', 'tipo_envio', 'presentacion']).agg({
        'cantidad_cajas': 'sum',
        'id': 'count'
    }).rename(columns={'id': 'numero_envios'}).reset_index()
    
    envios_diarios = envios.groupby('fecha').agg({
        'cantidad_cajas': 'sum',
        'id': 'count'
    }).rename(columns={'id': 'envios'}).reset_index()
    
    if 'tipo_envio' in envios.columns:
        envios_diarios['nacional'] = envios[envios['tipo_envio'] == 'Nacional'].groupby('fecha')['cantidad_cajas'].sum()
        envios_diarios['exportacion'] = envios[envios['tipo_envio'] == 'Exportación'].groupby('fecha')['cantidad_cajas'].sum()
        envios_diarios = envios_diarios.fillna(0)
    
    top_trabajadores_envian = envios.groupby('trabajador_envia').agg({
        'cantidad_cajas': 'sum',
        'id': 'count'
    }).rename(columns={'id': 'numero_envios', 'cantidad_cajas': 'cajas_enviadas'}).reset_index().head(10)
    
    resumen_presentacion = envios.groupby('presentacion').agg({
        'cantidad_cajas': 'sum',
        'id': 'count'
    }).rename(columns={'id': 'envios'}).reset_index()
    
    return {
        'total_cajas': total_cajas,
        'envios_por_invernadero': envios_por_invernadero,
        'envios_diarios': envios_diarios,
        'top_trabajadores_envian': top_trabajadores_envian,
        'resumen_presentacion': resumen_presentacion
    }

def get_stats_cosecha():
    cosechas = get_cosechas()
    
    if cosechas.empty:
        return {
            'total_cosechas': 0,
            'total_clams': 0,
            'total_cajas': 0,
            'cajas_enviadas': 0,
            'cajas_disponibles': 0,
            'cosechas_por_tipo': pd.DataFrame()
        }
    
    total_cosechas = len(cosechas)
    total_clams = cosechas['cantidad_clams'].sum() if 'cantidad_clams' in cosechas.columns else 0
    total_cajas = cosechas['numero_cajas'].sum() if 'numero_cajas' in cosechas.columns else 0
    cajas_enviadas = cosechas['cajas_enviadas'].sum() if 'cajas_enviadas' in cosechas.columns else 0
    
    cosechas_por_tipo = cosechas.groupby('tipo_cosecha').agg({
        'id': 'count',
        'cantidad_clams': 'sum'
    }).rename(columns={'id': 'cantidad'}).reset_index()
    
    if 'tipo_cosecha' in cosechas_por_tipo.columns:
        cosechas_por_tipo['cajas'] = cosechas_por_tipo.apply(
            lambda row: row['cantidad_clams'] / 12 if row['tipo_cosecha'] == 'Exportación' else row['cantidad_clams'] / 6, axis=1
        )
    
    return {
        'total_cosechas': total_cosechas,
        'total_clams': total_clams,
        'total_cajas': total_cajas,
        'cajas_enviadas': cajas_enviadas,
        'cajas_disponibles': total_cajas - cajas_enviadas,
        'cosechas_por_tipo': cosechas_por_tipo
    }

# ==========================================
# FUNCIONES DE CONTROL DE ASISTENCIA (SUPABASE)
# ==========================================

def registrar_evento_asistencia(trabajador_id, invernadero_id, tipo_evento):
    try:
        fecha_actual = datetime.now().date()
        hora_actual = datetime.now().time().strftime("%H:%M:%S")
        
        # Buscar registro activo
        registro_activo = supabase.table('asistencia').select('*')\
            .eq('trabajador_id', trabajador_id)\
            .eq('fecha', fecha_actual.isoformat())\
            .neq('estado', 'finalizado')\
            .order('id', desc=True)\
            .limit(1)\
            .execute()
        
        if tipo_evento == 'entrada_invernadero':
            if registro_activo.data:
                return False, "❌ Ya tienes un registro activo hoy"
            
            supabase.table('asistencia').insert({
                'trabajador_id': trabajador_id,
                'invernadero_id': invernadero_id,
                'fecha': fecha_actual.isoformat(),
                'hora_entrada': hora_actual,
                'estado': 'activo',
                'tipo_movimiento': tipo_evento
            }).execute()
            
            supabase.table('registros_asistencia').insert({
                'trabajador_id': trabajador_id,
                'invernadero_id': invernadero_id,
                'fecha': fecha_actual.isoformat(),
                'hora': hora_actual,
                'tipo_evento': tipo_evento
            }).execute()
            
        elif tipo_evento == 'salida_comer':
            if not registro_activo.data:
                return False, "❌ No hay registro de entrada activo"
            
            reg = registro_activo.data[0]
            if reg.get('hora_entrada') is None:
                return False, "❌ Primero debes registrar entrada"
            if reg.get('hora_salida_comida') is not None:
                return False, "❌ Ya registraste salida a comer"
            
            supabase.table('asistencia').update({
                'hora_salida_comida': hora_actual,
                'estado': 'comida',
                'tipo_movimiento': tipo_evento
            }).eq('id', reg['id']).execute()
            
            supabase.table('registros_asistencia').insert({
                'trabajador_id': trabajador_id,
                'invernadero_id': reg.get('invernadero_id'),
                'fecha': fecha_actual.isoformat(),
                'hora': hora_actual,
                'tipo_evento': tipo_evento
            }).execute()
            
        elif tipo_evento == 'regreso_comida':
            if not registro_activo.data:
                return False, "❌ No hay registro de entrada activo"
            
            reg = registro_activo.data[0]
            if reg.get('hora_salida_comida') is None:
                return False, "❌ Primero debes registrar salida a comer"
            if reg.get('hora_entrada_comida') is not None:
                return False, "❌ Ya registraste regreso de comida"
            
            supabase.table('asistencia').update({
                'hora_entrada_comida': hora_actual,
                'estado': 'activo',
                'tipo_movimiento': tipo_evento
            }).eq('id', reg['id']).execute()
            
            supabase.table('registros_asistencia').insert({
                'trabajador_id': trabajador_id,
                'invernadero_id': reg.get('invernadero_id'),
                'fecha': fecha_actual.isoformat(),
                'hora': hora_actual,
                'tipo_evento': tipo_evento
            }).execute()
            
        elif tipo_evento == 'salida_invernadero':
            if not registro_activo.data:
                return False, "❌ No hay registro de entrada activo"
            
            reg = registro_activo.data[0]
            if reg.get('hora_entrada') is None:
                return False, "❌ Primero debes registrar entrada"
            if reg.get('hora_salida') is not None:
                return False, "❌ Ya registraste salida"
            
            supabase.table('asistencia').update({
                'hora_salida': hora_actual,
                'estado': 'finalizado',
                'tipo_movimiento': tipo_evento
            }).eq('id', reg['id']).execute()
            
            supabase.table('registros_asistencia').insert({
                'trabajador_id': trabajador_id,
                'invernadero_id': reg.get('invernadero_id'),
                'fecha': fecha_actual.isoformat(),
                'hora': hora_actual,
                'tipo_evento': tipo_evento
            }).execute()
        
        invalidar_cache()
        
        mensajes = {
            'entrada_invernadero': "✅ Entrada registrada correctamente",
            'salida_comer': "✅ Salida a comer registrada",
            'regreso_comida': "✅ Regreso de comida registrado",
            'salida_invernadero': "✅ Salida registrada correctamente"
        }
        
        return True, mensajes.get(tipo_evento, "✅ Evento registrado correctamente")
        
    except Exception as e:
        return False, f"❌ Error al registrar: {str(e)}"

def get_estado_asistencia_actual(trabajador_id):
    try:
        fecha_actual = datetime.now().date()
        
        result = supabase.table('asistencia').select("""
            *,
            invernaderos:invernadero_id (nombre)
        """)\
            .eq('trabajador_id', trabajador_id)\
            .eq('fecha', fecha_actual.isoformat())\
            .neq('estado', 'finalizado')\
            .order('id', desc=True)\
            .limit(1)\
            .execute()
        
        if result.data:
            reg = result.data[0]
            return {
                'id': reg['id'],
                'estado': reg['estado'],
                'hora_entrada': reg.get('hora_entrada'),
                'hora_salida_comida': reg.get('hora_salida_comida'),
                'hora_entrada_comida': reg.get('hora_entrada_comida'),
                'hora_salida': reg.get('hora_salida'),
                'invernadero': reg['invernaderos']['nombre'] if reg.get('invernaderos') else None
            }
        return None
    except Exception as e:
        st.error(f"Error al obtener estado: {str(e)}")
        return None

def get_registros_asistencia(filtros=None):
    try:
        query = supabase.table('registros_asistencia').select("""
            *,
            trabajadores:trabajador_id (nombre, apellido_paterno),
            invernaderos:invernadero_id (nombre)
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
            trabajador = ""
            if row['trabajadores']:
                trabajador = f"{row['trabajadores'].get('nombre', '')} {row['trabajadores'].get('apellido_paterno', '')}"
            
            tipo_evento_display = {
                'entrada_invernadero': 'Entrada a Invernadero',
                'salida_comer': 'Salida a Comer',
                'regreso_comida': 'Regreso de Comida',
                'salida_invernadero': 'Salida'
            }.get(row['tipo_evento'], row['tipo_evento'])
            
            data.append({
                'id': row['id'],
                'trabajador': trabajador,
                'trabajador_id': row['trabajador_id'],
                'invernadero': row['invernaderos']['nombre'] if row['invernaderos'] else None,
                'fecha': row['fecha'],
                'hora': row['hora'],
                'tipo_evento': tipo_evento_display,
                'fecha_registro': f"{row['fecha']} {row['hora']}"
            })
        
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error al obtener registros: {str(e)}")
        return pd.DataFrame()

def get_resumen_asistencia_dia(fecha=None):
    if not fecha:
        fecha = datetime.now().date()
    
    try:
        # Obtener trabajadores activos
        trabajadores = get_all_workers()
        
        # Obtener asistencias
        asistencias = supabase.table('asistencia').select("""
            *,
            invernaderos:invernadero_id (nombre)
        """).eq('fecha', fecha.isoformat()).execute()
        
        asis_dict = {}
        for row in asistencias.data:
            asis_dict[row['trabajador_id']] = row
        
        # Obtener descansos
        descansos = supabase.table('descansos').select('*')\
            .eq('fecha', fecha.isoformat()).execute()
        descansos_dict = {row['trabajador_id']: row for row in descansos.data}
        
        # Obtener incidencias
        incidencias = supabase.table('incidencias').select('*')\
            .eq('fecha', fecha.isoformat()).execute()
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
                inc_tipo = incidencia.get('tipo_incidencia', '')
                inc_subtipo = incidencia.get('subtipo', '')
                estado_actual = f"Incidencia: {inc_tipo}"
                if inc_subtipo:
                    estado_actual += f" - {inc_subtipo}"
            elif not asistencia.get('hora_entrada'):
                estado_actual = 'Falta'
            elif not asistencia.get('hora_salida'):
                estado_actual = 'En invernadero'
            elif asistencia.get('hora_salida_comida') and not asistencia.get('hora_entrada_comida'):
                estado_actual = 'En comida'
            else:
                estado_actual = 'Finalizado'
            
            data.append({
                'trabajador_id': trabajador_id,
                'trabajador': f"{trabajador['nombre']} {trabajador['apellido_paterno']}",
                'hora_entrada': asistencia.get('hora_entrada'),
                'hora_salida_comida': asistencia.get('hora_salida_comida'),
                'hora_entrada_comida': asistencia.get('hora_entrada_comida'),
                'hora_salida': asistencia.get('hora_salida'),
                'invernadero': asistencia.get('invernaderos', {}).get('nombre') if asistencia.get('invernaderos') else None,
                'estado_actual': estado_actual
            })
        
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error al obtener resumen: {str(e)}")
        return pd.DataFrame()

def get_estadisticas_asistencia(fecha_inicio=None, fecha_fin=None):
    if not fecha_inicio:
        fecha_inicio = datetime.now().date() - timedelta(days=30)
    if not fecha_fin:
        fecha_fin = datetime.now().date()
    
    try:
        registros = get_registros_asistencia({'fecha_inicio': fecha_inicio, 'fecha_fin': fecha_fin})
        
        if registros.empty:
            return {
                'registros_por_tipo': pd.DataFrame(),
                'horas_promedio': pd.DataFrame(),
                'tiempo_invernadero': pd.DataFrame(),
                'asistencia_diaria': pd.DataFrame(),
                'faltas_descansos': pd.DataFrame()
            }
        
        registros_por_tipo = registros.groupby('tipo_evento').size().reset_index(name='cantidad')
        
        # Obtener horas promedio (requiere cálculo adicional)
        asistencias = supabase.table('asistencia').select('trabajador_id, fecha, hora_entrada, hora_salida, hora_entrada_comida, hora_salida_comida')\
            .gte('fecha', fecha_inicio.isoformat())\
            .lte('fecha', fecha_fin.isoformat())\
            .execute()
        
        # Calcular horas trabajadas
        horas_data = []
        for row in asistencias.data:
            if row.get('hora_entrada') and row.get('hora_salida'):
                # Convertir horas a minutos para cálculo
                try:
                    entrada = datetime.strptime(row['hora_entrada'], '%H:%M:%S')
                    salida = datetime.strptime(row['hora_salida'], '%H:%M:%S')
                    horas = (salida - entrada).seconds / 3600
                    
                    # Restar comida
                    if row.get('hora_salida_comida') and row.get('hora_entrada_comida'):
                        salida_comida = datetime.strptime(row['hora_salida_comida'], '%H:%M:%S')
                        entrada_comida = datetime.strptime(row['hora_entrada_comida'], '%H:%M:%S')
                        horas -= (entrada_comida - salida_comida).seconds / 3600
                    
                    horas_data.append({'trabajador_id': row['trabajador_id'], 'horas': horas})
                except:
                    pass
        
        if horas_data:
            horas_df = pd.DataFrame(horas_data)
            horas_promedio = horas_df.groupby('trabajador_id')['horas'].mean().reset_index()
            
            # Unir con nombres
            trabajadores = get_all_workers()
            if not trabajadores.empty:
                horas_promedio = horas_promedio.merge(
                    trabajadores[['id', 'nombre', 'apellido_paterno']],
                    left_on='trabajador_id',
                    right_on='id'
                )
                horas_promedio['trabajador'] = horas_promedio['nombre'] + ' ' + horas_promedio['apellido_paterno']
        else:
            horas_promedio = pd.DataFrame()
        
        # Asistencia diaria
        asistencia_diaria = registros.groupby('fecha').size().reset_index(name='total_registros')
        
        return {
            'registros_por_tipo': registros_por_tipo,
            'horas_promedio': horas_promedio,
            'tiempo_invernadero': pd.DataFrame(),
            'asistencia_diaria': asistencia_diaria,
            'faltas_descansos': pd.DataFrame()
        }
    except Exception as e:
        st.error(f"Error al obtener estadísticas: {str(e)}")
        return {
            'registros_por_tipo': pd.DataFrame(),
            'horas_promedio': pd.DataFrame(),
            'tiempo_invernadero': pd.DataFrame(),
            'asistencia_diaria': pd.DataFrame(),
            'faltas_descansos': pd.DataFrame()
        }

# ==========================================
# FUNCIONES DE DESCANSO (SUPABASE)
# ==========================================

def registrar_descanso(trabajador_id, fecha, tipo_descanso, observaciones=""):
    try:
        result = supabase.table('descansos').upsert({
            'trabajador_id': trabajador_id,
            'fecha': fecha.isoformat() if isinstance(fecha, date) else fecha,
            'tipo_descanso': tipo_descanso,
            'observaciones': observaciones
        }).execute()
        
        invalidar_cache()
        return True, f"✅ Descanso registrado: {tipo_descanso}"
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

def get_descansos(fecha_inicio=None, fecha_fin=None):
    try:
        query = supabase.table('descansos').select("""
            *,
            trabajadores:trabajador_id (nombre, apellido_paterno)
        """)
        
        if fecha_inicio:
            query = query.gte('fecha', fecha_inicio.isoformat() if isinstance(fecha_inicio, date) else fecha_inicio)
        if fecha_fin:
            query = query.lte('fecha', fecha_fin.isoformat() if isinstance(fecha_fin, date) else fecha_fin)
        
        result = query.order('fecha', desc=True).execute()
        
        data = []
        for row in result.data:
            trabajador = ""
            if row['trabajadores']:
                trabajador = f"{row['trabajadores'].get('nombre', '')} {row['trabajadores'].get('apellido_paterno', '')}"
            
            data.append({
                'id': row['id'],
                'trabajador_id': row['trabajador_id'],
                'trabajador': trabajador,
                'fecha': row['fecha'],
                'tipo_descanso': row['tipo_descanso'],
                'observaciones': row.get('observaciones', '')
            })
        
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error al obtener descansos: {str(e)}")
        return pd.DataFrame()

# ==========================================
# FUNCIONES DE INCIDENCIAS (SUPABASE)
# ==========================================

def registrar_incidencia(trabajador_id, fecha, tipo_incidencia, subtipo, horas_afectadas, justificada, observaciones, registrado_por):
    try:
        result = supabase.table('incidencias').insert({
            'trabajador_id': trabajador_id,
            'fecha': fecha.isoformat() if isinstance(fecha, date) else fecha,
            'tipo_incidencia': tipo_incidencia,
            'subtipo': subtipo,
            'horas_afectadas': horas_afectadas,
            'justificada': justificada,
            'observaciones': observaciones,
            'registrado_por': registrado_por
        }).execute()
        
        invalidar_cache()
        return True, f"✅ Incidencia registrada: {tipo_incidencia}"
    except Exception as e:
        return False, f"❌ Error al registrar: {str(e)}"

def get_incidencias(fecha_inicio=None, fecha_fin=None, trabajador_id=None):
    try:
        query = supabase.table('incidencias').select("""
            *,
            trabajadores:trabajador_id (nombre, apellido_paterno)
        """)
        
        if fecha_inicio:
            query = query.gte('fecha', fecha_inicio.isoformat() if isinstance(fecha_inicio, date) else fecha_inicio)
        if fecha_fin:
            query = query.lte('fecha', fecha_fin.isoformat() if isinstance(fecha_fin, date) else fecha_fin)
        if trabajador_id:
            query = query.eq('trabajador_id', trabajador_id)
        
        result = query.order('fecha', desc=True).order('created_at', desc=True).execute()
        
        data = []
        for row in result.data:
            trabajador = ""
            if row['trabajadores']:
                trabajador = f"{row['trabajadores'].get('nombre', '')} {row['trabajadores'].get('apellido_paterno', '')}"
            
            data.append({
                'id': row['id'],
                'trabajador_id': row['trabajador_id'],
                'trabajador': trabajador,
                'fecha': row['fecha'],
                'tipo_incidencia': row['tipo_incidencia'],
                'subtipo': row.get('subtipo'),
                'horas_afectadas': row.get('horas_afectadas', 0),
                'justificada': row.get('justificada', False),
                'observaciones': row.get('observaciones', ''),
                'registrado_por': row.get('registrado_por', ''),
                'created_at': row.get('created_at')
            })
        
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error al obtener incidencias: {str(e)}")
        return pd.DataFrame()

def get_resumen_incidencias(fecha_inicio=None, fecha_fin=None):
    incidencias = get_incidencias(fecha_inicio, fecha_fin)
    
    if incidencias.empty:
        return {'resumen_tipo': pd.DataFrame(), 'resumen_trabajador': pd.DataFrame()}
    
    resumen_tipo = incidencias.groupby('tipo_incidencia').agg({
        'id': 'count',
        'justificada': lambda x: sum(x),
        'horas_afectadas': 'sum'
    }).rename(columns={'id': 'cantidad'}).reset_index()
    
    resumen_tipo['injustificadas'] = resumen_tipo['cantidad'] - resumen_tipo['justificada']
    
    return {'resumen_tipo': resumen_tipo, 'resumen_trabajador': pd.DataFrame()}

# ==========================================
# FUNCIONES DE MERMA (SUPABASE)
# ==========================================

def registrar_merma(invernadero_id, supervisor_nombre, kilos_merma, tipo_merma, observaciones, registrado_por):
    try:
        fecha_actual = datetime.now().date()
        hora_actual = datetime.now().time().strftime("%H:%M:%S")
        semana_actual = fecha_actual.isocalendar()[1]
        
        result = supabase.table('merma').insert({
            'fecha': fecha_actual.isoformat(),
            'hora': hora_actual,
            'semana': semana_actual,
            'invernadero_id': invernadero_id,
            'supervisor_nombre': supervisor_nombre,
            'kilos_merma': kilos_merma,
            'tipo_merma': tipo_merma,
            'observaciones': observaciones,
            'registrado_por': registrado_por
        }).execute()
        
        invalidar_cache()
        return True, "✅ Merma registrada correctamente"
    except Exception as e:
        return False, f"❌ Error al registrar: {str(e)}"

def get_merma(fecha_inicio=None, fecha_fin=None, invernadero_id=None):
    try:
        query = supabase.table('merma').select("""
            *,
            invernaderos:invernadero_id (nombre)
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
            data.append({
                'id': row['id'],
                'fecha': row['fecha'],
                'hora': row['hora'],
                'semana': row['semana'],
                'invernadero_id': row['invernadero_id'],
                'invernadero_nombre': row['invernaderos']['nombre'] if row['invernaderos'] else 'Desconocido',
                'supervisor_nombre': row['supervisor_nombre'],
                'kilos_merma': row['kilos_merma'],
                'tipo_merma': row['tipo_merma'],
                'observaciones': row.get('observaciones', ''),
                'registrado_por': row.get('registrado_por', '')
            })
        
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error al obtener merma: {str(e)}")
        return pd.DataFrame()

def get_stats_merma(fecha_inicio=None, fecha_fin=None):
    merma = get_merma(fecha_inicio, fecha_fin)
    
    if merma.empty:
        return {
            'total_merma': 0,
            'merma_por_invernadero': pd.DataFrame(),
            'merma_por_tipo': pd.DataFrame(),
            'merma_diaria': pd.DataFrame(),
            'top_supervisores': pd.DataFrame()
        }
    
    total_merma = merma['kilos_merma'].sum() if 'kilos_merma' in merma.columns else 0
    
    merma_por_invernadero = merma.groupby('invernadero_nombre').agg({
        'kilos_merma': 'sum',
        'id': 'count'
    }).rename(columns={'id': 'cantidad_registros'}).reset_index()
    
    if 'kilos_merma' in merma_por_invernadero.columns:
        merma_por_invernadero['promedio_merma'] = merma_por_invernadero['kilos_merma'] / merma_por_invernadero['cantidad_registros']
    
    merma_por_tipo = merma.groupby('tipo_merma').agg({
        'kilos_merma': 'sum',
        'id': 'count'
    }).rename(columns={'id': 'cantidad_registros'}).reset_index()
    
    merma_diaria = merma.groupby('fecha').agg({
        'kilos_merma': 'sum',
        'id': 'count'
    }).rename(columns={'id': 'registros'}).reset_index()
    
    top_supervisores = merma.groupby('supervisor_nombre').agg({
        'kilos_merma': 'sum',
        'id': 'count'
    }).rename(columns={'id': 'cantidad_registros'}).reset_index().head(10)
    
    return {
        'total_merma': total_merma,
        'merma_por_invernadero': merma_por_invernadero,
        'merma_por_tipo': merma_por_tipo,
        'merma_diaria': merma_diaria,
        'top_supervisores': top_supervisores
    }

# ==========================================
# FUNCIONES DE PROYECCIONES (SUPABASE)
# ==========================================

PESO_CAJA = 2.16

def calcular_porcentaje_merma_filtrado(kilos_enviados, cosecha_total):
    if cosecha_total <= 0:
        return 0
    cajas_enviadas = kilos_enviados / PESO_CAJA
    return (cajas_enviadas / cosecha_total) * 100

def obtener_porcentaje_merma_filtrado(df_cosechas, df_envios):
    if df_cosechas.empty or df_envios.empty:
        return 0
    
    cosecha_total_kilos = df_cosechas['cantidad_clams'].sum() if not df_cosechas.empty else 0
    kilos_enviados = df_envios['cantidad_cajas'].sum() * PESO_CAJA if not df_envios.empty else 0
    
    if kilos_enviados > 0 and cosecha_total_kilos > 0:
        return calcular_porcentaje_merma_filtrado(kilos_enviados, cosecha_total_kilos)
    return 0

def registrar_proyeccion(semana, cajas_proyectadas, registrado_por, observaciones=""):
    try:
        result = supabase.table('proyecciones_cajas').upsert({
            'semana': semana,
            'cajas_proyectadas': cajas_proyectadas,
            'registrado_por': registrado_por,
            'observaciones': observaciones
        }).execute()
        
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
        
        data = []
        for row in result.data:
            data.append({
                'id': row['id'],
                'semana': row['semana'],
                'cajas_proyectadas': row['cajas_proyectadas'],
                'fecha_registro': row['fecha_registro'],
                'registrado_por': row.get('registrado_por', ''),
                'observaciones': row.get('observaciones', '')
            })
        
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error al obtener proyecciones: {str(e)}")
        return pd.DataFrame()

def get_comparativa_proyeccion_real_con_filtros(semana_inicio=None, semana_fin=None, tipo_cosecha=None, presentacion=None):
    try:
        # Obtener producción real
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
        
        # Agrupar por semana
        real_dict = {}
        for row in cosechas.data:
            semana = row['semana']
            real_dict[semana] = real_dict.get(semana, 0) + row['numero_cajas']
        
        # Obtener proyecciones
        proyecciones = get_proyecciones()
        
        # Combinar
        semanas = set(real_dict.keys()) | set(proyecciones['semana'].tolist() if not proyecciones.empty else [])
        semanas = sorted([s for s in semanas if s >= (semana_inicio or 1) and s <= (semana_fin or 52)])
        
        data = []
        for semana in semanas:
            cajas_reales = real_dict.get(semana, 0)
            cajas_proyectadas = 0
            if not proyecciones.empty:
                proy_filt = proyecciones[proyecciones['semana'] == semana]
                if not proy_filt.empty:
                    cajas_proyectadas = proy_filt.iloc[0]['cajas_proyectadas']
            
            diferencia = cajas_reales - cajas_proyectadas
            porcentaje_desviacion = (diferencia / cajas_proyectadas * 100) if cajas_proyectadas > 0 else 0
            
            data.append({
                'semana': semana,
                'cajas_proyectadas': cajas_proyectadas,
                'cajas_reales': cajas_reales,
                'diferencia': diferencia,
                'porcentaje_desviacion': porcentaje_desviacion,
                'estado': '✅ Superávit' if diferencia >= 0 else '⚠️ Déficit'
            })
        
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error al obtener comparativa: {str(e)}")
        return pd.DataFrame()

def get_resumen_proyecciones_total_con_filtros_dashboard(df_cosechas):
    try:
        proyecciones = get_proyecciones()
        
        total_real = df_cosechas['numero_cajas'].sum() if not df_cosechas.empty else 0
        total_proyectado = proyecciones['cajas_proyectadas'].sum() if not proyecciones.empty else 0
        
        diferencia = total_real - total_proyectado
        porcentaje = (diferencia / total_proyectado * 100) if total_proyectado > 0 else 0
        
        return {
            'total_proyectado': total_proyectado,
            'total_real': total_real,
            'diferencia': diferencia,
            'porcentaje_desviacion': porcentaje
        }
    except Exception as e:
        return {
            'total_proyectado': 0,
            'total_real': 0,
            'diferencia': 0,
            'porcentaje_desviacion': 0
        }

# ==========================================
# FUNCIONES DE QR Y ESCANEO (SUPABASE)
# ==========================================

def procesar_qr_data(qr_data):
    try:
        id_match = re.search(r'[?&]id=([^&]+)', qr_data)
        nombre_match = re.search(r'[?&]nombre=([^&]+)', qr_data)
        
        if id_match and nombre_match:
            id_trabajador = id_match.group(1)
            nombre = nombre_match.group(1)
            nombre = nombre.replace('%20', ' ').replace('+', ' ')
            return id_trabajador, nombre
        
        if '|' in qr_data:
            partes = qr_data.split('|')
            if len(partes) >= 2:
                return partes[0], partes[1]
        
        return None, None
    except Exception:
        return None, None

def registrar_escaneo_qr(id_trabajador, nombre_trabajador, tipo_evento="entrada", invernadero_id=None):
    try:
        fecha_actual = datetime.now().strftime("%d/%m/%Y")
        hora_actual = datetime.now().strftime("%H:%M:%S")
        
        result = supabase.table('registros_escaneo').insert({
            'id_trabajador': str(id_trabajador),
            'nombre_trabajador': nombre_trabajador,
            'fecha_escaneo': fecha_actual,
            'hora_escaneo': hora_actual,
            'tipo_evento': tipo_evento,
            'invernadero_id': invernadero_id
        }).execute()
        
        invalidar_cache()
        return True, f"✅ {nombre_trabajador} registrado exitosamente"
    except Exception as e:
        return False, f"❌ Error al registrar: {str(e)}"

def generar_qr_trabajador_simple(id_trabajador, nombre, url_base="http://localhost:8501"):
    url = f"{url_base}?id={id_trabajador}&nombre={nombre.replace(' ', '%20')}"
    
    qr = qrcode.QRCode(
        version=1,
        box_size=10,
        border=5,
        error_correction=qrcode.constants.ERROR_CORRECT_L
    )
    qr.add_data(url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    return img_bytes

def escanear_qr_con_camara(tipo_evento="asistencia", mostrar_invernadero=False):
    st.markdown("### 📷 Escaneo Automático con Cámara")
    
    if 'qr_scan_active' not in st.session_state:
        st.session_state.qr_scan_active = True
        st.session_state.qr_scanned = False
        st.session_state.scanned_data = None
        st.session_state.invernadero_id = None
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🔄 Reiniciar Escaneo", use_container_width=True, key="btn_reiniciar_scan"):
            st.session_state.qr_scan_active = True
            st.session_state.qr_scanned = False
            st.session_state.scanned_data = None
            st.session_state.invernadero_id = None
            st.rerun()
    
    if st.session_state.qr_scan_active and not st.session_state.qr_scanned:
        try:
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                st.error("❌ No se pudo acceder a la cámara")
                return
            
            st.success("✅ Cámara activada. Acerca un código QR a la cámara.")
            video_placeholder = st.empty()
            status_placeholder = st.empty()
            status_placeholder.info("🔍 Buscando código QR...")
            
            start_time = time.time()
            timeout = 60
            last_qr = None
            
            while time.time() - start_time < timeout and not st.session_state.qr_scanned:
                ret, frame = cap.read()
                if not ret:
                    break
                
                qr_codes = decode(frame)
                
                if qr_codes:
                    for qr in qr_codes:
                        qr_data = qr.data.decode('utf-8')
                        if qr_data != last_qr:
                            last_qr = qr_data
                            id_trabajador, nombre = procesar_qr_data(qr_data)
                            
                            if id_trabajador and nombre:
                                trabajador = get_worker_by_id(id_trabajador)
                                if trabajador:
                                    st.session_state.scanned_data = {'id': id_trabajador, 'nombre': nombre}
                                    st.session_state.qr_scan_active = False
                                    st.session_state.qr_scanned = True
                                    cap.release()
                                    cv2.destroyAllWindows()
                                    st.rerun()
                                else:
                                    status_placeholder.warning(f"⚠️ Trabajador no encontrado: {nombre}")
                                    time.sleep(2)
                            else:
                                status_placeholder.warning("⚠️ QR no válido")
                                time.sleep(1)
                    
                    for qr in qr_codes:
                        points = qr.polygon
                        if points:
                            pts = np.array(points, np.int32)
                            pts = pts.reshape((-1, 1, 2))
                            cv2.polylines(frame, [pts], True, (0, 255, 0), 3)
                    cv2.putText(frame, "QR Detectado!", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                else:
                    remaining = int(timeout - (time.time() - start_time))
                    cv2.putText(frame, f"Buscando QR... ({remaining}s)", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                video_placeholder.image(frame_rgb, channels="RGB", use_container_width=True)
                time.sleep(0.03)
            
            cap.release()
            cv2.destroyAllWindows()
            if not st.session_state.qr_scanned:
                status_placeholder.warning("⏰ Tiempo agotado. No se detectó QR.")
                if st.button("🔄 Reintentar", use_container_width=True, key="btn_reintentar_scan"):
                    st.session_state.qr_scan_active = True
                    st.rerun()
                    
        except Exception as e:
            st.error(f"Error con la cámara: {str(e)}")
            if 'cap' in locals():
                cap.release()
            cv2.destroyAllWindows()
            st.session_state.qr_scan_active = False
    
    elif st.session_state.scanned_data:
        datos = st.session_state.scanned_data
        st.success(f"✅ QR Detectado: {datos['nombre']} (ID: {datos['id']})")
        
        if tipo_evento == "cosecha":
            st.markdown("### 📋 Registrar Cosecha")
            
            invernadero_id = None
            if mostrar_invernadero:
                invernaderos = get_invernaderos()
                if invernaderos:
                    invernadero = st.selectbox("🏭 Invernadero:", invernaderos, format_func=lambda x: f"{x[1]} - {x[2]}", key="invernadero_qr_scan")
                    invernadero_id = invernadero[0]
                    st.session_state.invernadero_id = invernadero_id
                else:
                    st.warning("No hay invernaderos registrados")
            
            fecha_actual = datetime.now()
            dias_espanol = {'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miércoles',
                            'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'Sábado', 'Sunday': 'Domingo'}
            dia_espanol = dias_espanol[fecha_actual.strftime('%A')]
            
            col1, col2, col3 = st.columns(3)
            with col1: st.write(f"**Fecha:** {fecha_actual.strftime('%d/%m/%Y')}")
            with col2: st.write(f"**Día:** {dia_espanol}")
            with col3: st.write(f"**Semana:** {fecha_actual.isocalendar()[1]}")
            
            col1, col2 = st.columns(2)
            with col1:
                tipo_cosecha = st.selectbox("Tipo de Cosecha:", ["Nacional", "Exportación"], key="tipo_cosecha_qr")
                if tipo_cosecha == "Nacional":
                    calidad = st.selectbox("Calidad:", ["Salmon", "Sobretono"], key="calidad_qr")
                else:
                    calidad = None
            
            with col2:
                if tipo_cosecha == "Exportación":
                    presentacion = st.selectbox("Presentación:", ["6 oz", "12 oz"], key="presentacion_qr")
                else:
                    presentacion = "6 oz"
                    st.info("✅ Presentación automática: 6 oz")
            
            cantidad_clams = st.number_input("Cantidad de Clams:", min_value=0.0, value=0.0, step=1.0, key="clams_qr")
            
            if presentacion == "12 oz":
                cajas_calculadas = cantidad_clams / 12 if cantidad_clams > 0 else 0
            else:
                cajas_calculadas = cantidad_clams / 6 if cantidad_clams > 0 else 0
            
            st.text_input("Número de Cajas:", value=f"{cajas_calculadas:.2f}", disabled=True, key="cajas_qr_display")
            
            if st.button("💾 Guardar Cosecha", type="primary", use_container_width=True, key="guardar_cosecha_qr"):
                if cantidad_clams <= 0:
                    st.error("Ingrese una cantidad válida de clams")
                elif not invernadero_id:
                    st.error("❌ Seleccione un invernadero antes de guardar")
                else:
                    data = {
                        'fecha': fecha_actual.date(), 
                        'dia': dia_espanol, 
                        'semana': fecha_actual.isocalendar()[1],
                        'trabajador_id': int(datos['id']), 
                        'invernadero_id': invernadero_id,
                        'tipo_cosecha': tipo_cosecha, 
                        'calidad': calidad,
                        'presentacion': presentacion,
                        'cantidad_clams': float(cantidad_clams)
                    }
                    success, msg = guardar_cosecha(data)
                    if success:
                        st.success(msg)
                        st.balloons()
                        st.session_state.scanned_data = None
                        st.session_state.qr_scan_active = True
                        st.rerun()
                    else:
                        st.error(msg)
        
        elif tipo_evento == "asistencia":
            st.markdown("### 📋 Registrar Evento de Asistencia")
            
            invernaderos = get_invernaderos()
            if invernaderos:
                invernadero = st.selectbox(
                    "🏭 Invernadero:", 
                    invernaderos, 
                    format_func=lambda x: f"{x[1]} - {x[2]}",
                    key="invernadero_asistencia_qr"
                )
                invernadero_id = invernadero[0]
            else:
                invernadero_id = None
                st.warning("No hay invernaderos registrados")
            
            tipo_evento_select = st.selectbox(
                "📌 Tipo de Evento:", 
                ["entrada_invernadero", "salida_comer", "regreso_comida", "salida_invernadero"],
                format_func=lambda x: {
                    'entrada_invernadero': '🚪 Entrada a Invernadero', 
                    'salida_comer': '🍽️ Salida a Comer',
                    'regreso_comida': '✅ Regreso de Comida', 
                    'salida_invernadero': '🚪 Salida'
                }[x],
                key="tipo_evento_asistencia_qr"
            )
            
            st.info(f"👤 Trabajador: {datos['nombre']} (ID: {datos['id']})")
            
            if st.button("✅ Registrar Evento", type="primary", use_container_width=True, key="registrar_evento_asistencia_qr"):
                if tipo_evento_select == 'entrada_invernadero' and not invernadero_id:
                    st.error("❌ Para entrada, debe seleccionar un invernadero")
                else:
                    success, msg = registrar_evento_asistencia(
                        int(datos['id']), 
                        invernadero_id if tipo_evento_select == 'entrada_invernadero' else None, 
                        tipo_evento_select
                    )
                    if success:
                        st.success(msg)
                        st.balloons()
                        st.session_state.scanned_data = None
                        st.session_state.qr_scan_active = True
                        st.rerun()
                    else:
                        st.error(msg)

# ==========================================
# FUNCIONES DE DASHBOARD Y REPORTES (SUPABASE)
# ==========================================

def get_dashboard_stats():
    try:
        # Contar trabajadores activos
        activos_result = supabase.table('trabajadores').select('id', count='exact').eq('estatus', 'activo').execute()
        total_activos = activos_result.count if activos_result.count else 0
        
        # Contar bajas
        bajas_result = supabase.table('trabajadores').select('id', count='exact').eq('estatus', 'baja').execute()
        total_bajas = bajas_result.count if bajas_result.count else 0
        
        # Ingresos del mes
        inicio_mes = datetime.today().replace(day=1).date()
        ingresos_result = supabase.table('trabajadores').select('id', count='exact')\
            .gte('fecha_alta', inicio_mes.isoformat()).execute()
        ingresos_mes = ingresos_result.count if ingresos_result.count else 0
        
        # Distribución por departamento
        deptos_result = supabase.table('trabajadores').select("""
            departamentos:departamento_id (nombre),
            id
        """).eq('estatus', 'activo').execute()
        
        deptos_dict = {}
        for row in deptos_result.data:
            depto_nombre = row['departamentos']['nombre'] if row['departamentos'] else 'Sin asignar'
            deptos_dict[depto_nombre] = deptos_dict.get(depto_nombre, 0) + 1
        
        df_deptos = pd.DataFrame([{'departamento': k, 'cantidad': v} for k, v in deptos_dict.items()])
        
        # Distribución por tipo de nómina
        nomina_result = supabase.table('trabajadores').select('tipo_nomina', count='exact')\
            .eq('estatus', 'activo')\
            .group_by('tipo_nomina')\
            .execute()
        
        df_nomina = pd.DataFrame(nomina_result.data) if nomina_result.data else pd.DataFrame()
        
        return {
            'total_activos': total_activos,
            'total_bajas': total_bajas,
            'ingresos_mes': ingresos_mes,
            'df_deptos': df_deptos,
            'df_nomina': df_nomina
        }
    except Exception as e:
        st.error(f"Error al obtener estadísticas: {str(e)}")
        return {
            'total_activos': 0,
            'total_bajas': 0,
            'ingresos_mes': 0,
            'df_deptos': pd.DataFrame(),
            'df_nomina': pd.DataFrame()
        }

def get_report_ingresos_semana():
    hoy = datetime.today()
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    fin_semana = inicio_semana + timedelta(days=6)
    
    try:
        result = supabase.table('trabajadores').select("""
            id, nombre, apellido_paterno, apellido_materno,
            fecha_alta, tipo_nomina,
            departamentos:departamento_id (nombre),
            subdepartamentos:subdepartamento_id (nombre),
            puestos:puesto_id (nombre)
        """)\
            .gte('fecha_alta', inicio_semana.date().isoformat())\
            .lte('fecha_alta', fin_semana.date().isoformat())\
            .order('fecha_alta', desc=True)\
            .execute()
        
        data = []
        for row in result.data:
            data.append({
                'id': row['id'],
                'nombre': row['nombre'],
                'apellido_paterno': row['apellido_paterno'],
                'apellido_materno': row['apellido_materno'],
                'fecha_alta': row['fecha_alta'],
                'departamento': row['departamentos']['nombre'] if row['departamentos'] else 'Sin asignar',
                'subdepartamento': row['subdepartamentos']['nombre'] if row['subdepartamentos'] else 'Sin asignar',
                'puesto': row['puestos']['nombre'] if row['puestos'] else 'Sin asignar',
                'tipo_nomina': row['tipo_nomina']
            })
        
        return pd.DataFrame(data), inicio_semana, fin_semana
    except Exception as e:
        st.error(f"Error al obtener ingresos: {str(e)}")
        return pd.DataFrame(), inicio_semana, fin_semana

def get_report_bajas_semana():
    hoy = datetime.today()
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    fin_semana = inicio_semana + timedelta(days=6)
    
    try:
        result = supabase.table('trabajadores').select("""
            id, nombre, apellido_paterno, apellido_materno,
            fecha_baja,
            departamentos:departamento_id (nombre),
            subdepartamentos:subdepartamento_id (nombre),
            puestos:puesto_id (nombre)
        """)\
            .gte('fecha_baja', inicio_semana.date().isoformat())\
            .lte('fecha_baja', fin_semana.date().isoformat())\
            .order('fecha_baja', desc=True)\
            .execute()
        
        data = []
        for row in result.data:
            data.append({
                'id': row['id'],
                'nombre': row['nombre'],
                'apellido_paterno': row['apellido_paterno'],
                'apellido_materno': row['apellido_materno'],
                'fecha_baja': row['fecha_baja'],
                'departamento': row['departamentos']['nombre'] if row['departamentos'] else 'Sin asignar',
                'subdepartamento': row['subdepartamentos']['nombre'] if row['subdepartamentos'] else 'Sin asignar',
                'puesto': row['puestos']['nombre'] if row['puestos'] else 'Sin asignar'
            })
        
        return pd.DataFrame(data), inicio_semana, fin_semana
    except Exception as e:
        st.error(f"Error al obtener bajas: {str(e)}")
        return pd.DataFrame(), inicio_semana, fin_semana

def get_report_nomina_activa(depto_nombre=None, subdepto_nombre=None):
    try:
        query = supabase.table('trabajadores').select("""
            id, nombre, apellido_paterno, apellido_materno,
            telefono, correo, fecha_alta, tipo_nomina,
            departamentos:departamento_id (nombre),
            subdepartamentos:subdepartamento_id (nombre),
            puestos:puesto_id (nombre)
        """).eq('estatus', 'activo')
        
        if depto_nombre and depto_nombre != "Todos":
            query = query.eq('departamentos.nombre', depto_nombre)
        if subdepto_nombre and subdepto_nombre != "Todos":
            query = query.eq('subdepartamentos.nombre', subdepto_nombre)
        
        result = query.order('apellido_paterno').execute()
        
        data = []
        for row in result.data:
            data.append({
                'id': row['id'],
                'nombre': row['nombre'],
                'apellido_paterno': row['apellido_paterno'],
                'apellido_materno': row['apellido_materno'],
                'departamento': row['departamentos']['nombre'] if row['departamentos'] else 'Sin asignar',
                'subdepartamento': row['subdepartamentos']['nombre'] if row['subdepartamentos'] else 'Sin asignar',
                'puesto': row['puestos']['nombre'] if row['puestos'] else 'Sin asignar',
                'tipo_nomina': row['tipo_nomina'],
                'fecha_alta': row['fecha_alta'],
                'telefono': row['telefono'],
                'correo': row['correo']
            })
        
        df = pd.DataFrame(data)
        
        if not df.empty:
            resumen = df.groupby('departamento').size().reset_index(name='cantidad')
        else:
            resumen = pd.DataFrame(columns=['departamento', 'cantidad'])
        
        return df, resumen
    except Exception as e:
        st.error(f"Error al obtener nómina: {str(e)}")
        return pd.DataFrame(), pd.DataFrame()

def export_to_excel(df, sheet_name="Datos"):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    output.seek(0)
    return output

# ==========================================
# FUNCIONES DE UI (INTERFAZ DE USUARIO)
# ==========================================

def mostrar_gestion_personal():
    st.header("👥 Gestión de Trabajadores")
    
    tab1, tab2 = st.tabs(["Alta de Trabajador", "Buscar/Editar/Baja"])
    
    with tab1:
        with st.form("form_alta", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                apellido_paterno = st.text_input("Apellido Paterno *", key="alta_apellido_paterno")
                nombre = st.text_input("Nombre *", key="alta_nombre")
                telefono = st.text_input("Teléfono (10 dígitos)", key="alta_telefono")
                
            with col2:
                apellido_materno = st.text_input("Apellido Materno", key="alta_apellido_materno")
                correo = st.text_input("Correo Electrónico", key="alta_correo")
                fecha_alta = st.date_input("Fecha de Alta *", datetime.now(), key="alta_fecha")
                
            with col3:
                st.write("")
                st.write("")
                st.info("* Campos obligatorios")
            
            st.markdown("---")
            
            col4, col5, col6 = st.columns(3)
            with col4:
                departamentos_list = get_departamentos_nombres()
                departamento = st.selectbox("Departamento *", departamentos_list if departamentos_list else ["Sin datos"], key="alta_departamento")
            with col5:
                subdepartamentos_list = get_subdepartamentos_nombres()
                subdepartamento = st.selectbox("Subdepartamento *", subdepartamentos_list if subdepartamentos_list else ["Sin datos"], key="alta_subdepartamento")
            with col6:
                tipo_nomina = st.selectbox("Tipo de Nómina *", ["especial", "imss"], key="alta_tipo_nomina")
            
            puestos_list = get_puestos_nombres()
            puesto = st.selectbox("Puesto *", puestos_list if puestos_list else ["Sin datos"], key="alta_puesto")
            
            if st.form_submit_button("💾 Guardar Trabajador", use_container_width=True):
                if not apellido_paterno or not nombre:
                    st.error("Complete campos obligatorios")
                elif telefono and not validar_telefono(telefono):
                    st.error("Teléfono debe tener 10 dígitos")
                elif correo and not validar_email(correo):
                    st.error("Email inválido")
                elif departamento == "Sin datos" or subdepartamento == "Sin datos" or puesto == "Sin datos":
                    st.error("Primero debe agregar departamentos, subdepartamentos y puestos en Catálogos")
                else:
                    data = {
                        "ap": apellido_paterno.strip().upper(),
                        "am": apellido_materno.strip().upper() if apellido_materno else None,
                        "nom": nombre.strip().upper(),
                        "cor": correo.strip() if correo else None,
                        "tel": telefono.strip() if telefono else None,
                        "fa": fecha_alta,
                        "departamento": departamento,
                        "subdepartamento": subdepartamento,
                        "tn": tipo_nomina,
                        "puesto": puesto
                    }
                    
                    success, msg = add_worker(data)
                    if success:
                        st.success(msg)
                        st.balloons()
                    else:
                        st.error(msg)
    
    with tab2:
        col1, col2 = st.columns([3, 1])
        with col1:
            search_term = st.text_input("Buscar:", placeholder="Nombre o apellido...", key="buscar_trabajador")
        with col2:
            estatus_filter = st.selectbox("Estatus", ["todos", "activo", "baja"], key="estatus_filtro")
        
        if st.button("🔍 Buscar", key="btn_buscar_personal", use_container_width=True):
            if search_term:
                results = search_workers(search_term, estatus_filter)
                
                if not results.empty:
                    st.success(f"Encontrados: {len(results)}")
                    
                    for idx, row in results.iterrows():
                        with st.expander(f"📋 {row['apellido_paterno']} {row['apellido_materno'] or ''}, {row['nombre']}"):
                            col1, col2, col3 = st.columns(3)
                            
                            with col1:
                                st.write(f"**ID:** {row['id']}")
                                st.write(f"**Email:** {row['correo'] or 'N/A'}")
                                st.write(f"**Tel:** {row['telefono'] or 'N/A'}")
                            
                            with col2:
                                st.write(f"**Depto:** {row['departamento']}")
                                st.write(f"**Puesto:** {row['puesto']}")
                                st.write(f"**Estatus:** {row['estatus']}")
                            
                            with col3:
                                if row['estatus'] == 'activo':
                                    if st.button("🚫 Dar Baja", key=f"baja_{row['id']}_{idx}"):
                                        st.session_state['baja_id'] = row['id']
                                        st.session_state['baja_nombre'] = row['nombre']
                                else:
                                    if st.button("🔄 Reactivar", key=f"reactivar_{row['id']}_{idx}"):
                                        success, msg = reactivar_trabajador(row['id'])
                                        if success:
                                            st.success(msg)
                                            st.rerun()
                                        else:
                                            st.error(msg)
                                
                                if st.button("✏️ Editar", key=f"edit_{row['id']}_{idx}"):
                                    st.session_state['editing_id'] = row['id']
                            
                            if 'baja_id' in st.session_state and st.session_state['baja_id'] == row['id']:
                                st.warning(f"¿Dar de baja a {st.session_state['baja_nombre']}?")
                                fecha = st.date_input("Fecha de baja", datetime.now(), key=f"fecha_baja_{row['id']}_{idx}")
                                col_yes, col_no = st.columns(2)
                                with col_yes:
                                    if st.button("✅ Confirmar", key=f"conf_baja_{row['id']}_{idx}"):
                                        success, msg = dar_baja(row['id'], fecha)
                                        if success:
                                            st.success(msg)
                                            del st.session_state['baja_id']
                                            del st.session_state['baja_nombre']
                                            st.rerun()
                                        else:
                                            st.error(msg)
                                with col_no:
                                    if st.button("❌ Cancelar", key=f"cancel_baja_{row['id']}_{idx}"):
                                        del st.session_state['baja_id']
                                        del st.session_state['baja_nombre']
                                        st.rerun()
                            
                            if 'editing_id' in st.session_state and st.session_state['editing_id'] == row['id']:
                                worker = get_worker_by_id(row['id'])
                                if worker:
                                    with st.form(f"form_edit_{row['id']}_{idx}"):
                                        st.subheader(f"Editando: {worker['nombre']} {worker['apellido_paterno']}")
                                        
                                        col_a, col_b = st.columns(2)
                                        
                                        with col_a:
                                            ap = st.text_input("Apellido Paterno", worker['apellido_paterno'], key=f"edit_ap_{row['id']}_{idx}")
                                            nom = st.text_input("Nombre", worker['nombre'], key=f"edit_nom_{row['id']}_{idx}")
                                            tel = st.text_input("Teléfono", worker['telefono'] or "", key=f"edit_tel_{row['id']}_{idx}")
                                        
                                        with col_b:
                                            am = st.text_input("Apellido Materno", worker['apellido_materno'] or "", key=f"edit_am_{row['id']}_{idx}")
                                            email = st.text_input("Email", worker['correo'] or "", key=f"edit_email_{row['id']}_{idx}")
                                        
                                        deptos = get_departamentos_nombres()
                                        depto = st.selectbox("Departamento", deptos,
                                                            index=deptos.index(worker['departamento_nombre']) if worker['departamento_nombre'] in deptos else 0,
                                                            key=f"edit_depto_{row['id']}_{idx}")
                                        
                                        subs = get_subdepartamentos_nombres()
                                        sub = st.selectbox("Subdepartamento", subs,
                                                          index=subs.index(worker['subdepartamento_nombre']) if worker['subdepartamento_nombre'] in subs else 0,
                                                          key=f"edit_sub_{row['id']}_{idx}")
                                        
                                        tipo = st.selectbox("Tipo Nómina", ["especial", "imss"],
                                                           index=0 if worker['tipo_nomina']=='especial' else 1,
                                                           key=f"edit_tipo_{row['id']}_{idx}")
                                        
                                        puestos = get_puestos_nombres()
                                        p = st.selectbox("Puesto", puestos,
                                                        index=puestos.index(worker['puesto_nombre']) if worker['puesto_nombre'] in puestos else 0,
                                                        key=f"edit_puesto_{row['id']}_{idx}")
                                        
                                        est = st.selectbox("Estatus", ["activo", "baja"], 
                                                          index=0 if worker['estatus']=='activo' else 1,
                                                          key=f"edit_estatus_{row['id']}_{idx}")
                                        
                                        col_buttons = st.columns(2)
                                        with col_buttons[0]:
                                            if st.form_submit_button("💾 Guardar Cambios"):
                                                data = {
                                                    'apellido_paterno': ap, 
                                                    'apellido_materno': am,
                                                    'nombre': nom, 
                                                    'correo': email, 
                                                    'telefono': tel,
                                                    'departamento': depto, 
                                                    'subdepartamento': sub,
                                                    'tipo_nomina': tipo, 
                                                    'puesto': p, 
                                                    'estatus': est
                                                }
                                                success, msg = update_worker(row['id'], data)
                                                if success:
                                                    st.success(msg)
                                                    del st.session_state['editing_id']
                                                    st.rerun()
                                                else:
                                                    st.error(msg)
                                        with col_buttons[1]:
                                            if st.form_submit_button("❌ Cancelar"):
                                                del st.session_state['editing_id']
                                                st.rerun()
                else:
                    st.info("No se encontraron resultados")
            else:
                st.warning("Ingresa un término de búsqueda")

def formulario_cosecha_manual():
    st.header("🌾 Registro de Cosecha Manual")
    
    fecha_actual = datetime.now()
    fecha_formateada = fecha_actual.strftime("%Y/%m/%d")
    semana_actual = fecha_actual.isocalendar()[1]
    dias_espanol = {'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miércoles',
                    'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'Sábado', 'Sunday': 'Domingo'}
    dia_espanol = dias_espanol[fecha_actual.strftime('%A')]
    
    col_fecha, col_dia, col_semana = st.columns(3)
    
    with col_fecha:
        st.markdown(f"""
        <div class="date-card">
            <div style="font-size: 12px; color: rgba(255,255,255,0.8);">📅 FECHA</div>
            <div style="font-size: 24px; font-weight: bold; color: white;">{fecha_formateada}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col_dia:
        st.markdown(f"""
        <div class="time-card">
            <div style="font-size: 12px; color: rgba(255,255,255,0.8);">📆 DÍA</div>
            <div style="font-size: 24px; font-weight: bold; color: white;">{dia_espanol}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col_semana:
        st.markdown(f"""
        <div class="week-card">
            <div style="font-size: 12px; color: rgba(255,255,255,0.8);">📆 SEMANA</div>
            <div style="font-size: 24px; font-weight: bold; color: white;">{semana_actual}</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    if 'clams_value' not in st.session_state:
        st.session_state.clams_value = 0.0
    if 'presentacion_actual' not in st.session_state:
        st.session_state.presentacion_actual = "6 oz"
    if 'cajas_calculadas' not in st.session_state:
        st.session_state.cajas_calculadas = 0.0
    
    def calcular_cajas():
        clams = st.session_state.clams_value
        if st.session_state.presentacion_actual == "12 oz":
            st.session_state.cajas_calculadas = clams / 12 if clams > 0 else 0
        else:
            st.session_state.cajas_calculadas = clams / 6 if clams > 0 else 0
    
    trabajadores = get_all_workers()
    if not trabajadores.empty:
        trabajador_seleccionado = st.selectbox(
            "Seleccionar trabajador:", 
            trabajadores.apply(lambda x: f"{x['id']} - {x['nombre']} {x['apellido_paterno']}", axis=1),
            key="trabajador_manual_cosecha"
        )
        trabajador_id = int(trabajador_seleccionado.split(' - ')[0]) if trabajador_seleccionado else None
    else:
        trabajador_id = None
    
    invernaderos = get_invernaderos()
    if invernaderos:
        invernadero_seleccionado = st.selectbox(
            "Invernadero *", 
            invernaderos, 
            format_func=lambda x: f"{x[1]} - {x[2]}",
            key="invernadero_manual_cosecha"
        )
        invernadero_id = invernadero_seleccionado[0]
    else:
        invernadero_id = None
        st.error("No hay invernaderos registrados")
    
    tipo_cosecha = st.radio("Tipo de Cosecha:", ["Nacional", "Exportación"], horizontal=True, key="tipo_cosecha_manual")
    
    if tipo_cosecha == "Nacional":
        calidad = st.selectbox("Calidad:", ["Salmon", "Sobretono"], key="calidad_manual")
        presentacion = "6 oz"
        st.info("✅ Presentación automática: 6 oz")
    else:
        calidad = None
        presentacion = st.selectbox("Presentación:", ["6 oz", "12 oz"], on_change=calcular_cajas, key="presentacion_manual")
        st.session_state.presentacion_actual = presentacion
    
    cantidad_clams = st.number_input("Cantidad de Clams:", min_value=0.0, value=st.session_state.clams_value, step=1.0, on_change=calcular_cajas, key="clams_manual")
    st.session_state.clams_value = cantidad_clams
    st.text_input("Número de Cajas:", value=f"{st.session_state.cajas_calculadas:.2f}", disabled=True, key="cajas_manual")
    
    if st.button("💾 Guardar Cosecha", type="primary", use_container_width=True, key="guardar_cosecha_manual"):
        if not trabajador_id:
            st.error("Seleccione un trabajador")
        elif not invernadero_id:
            st.error("Seleccione un invernadero")
        elif cantidad_clams <= 0:
            st.error("Ingrese una cantidad válida de clams")
        else:
            data = {
                'fecha': fecha_actual.date(), 
                'dia': dia_espanol, 
                'semana': fecha_actual.isocalendar()[1],
                'trabajador_id': trabajador_id, 
                'invernadero_id': invernadero_id,
                'tipo_cosecha': tipo_cosecha,
                'calidad': calidad, 
                'presentacion': presentacion,
                'cantidad_clams': float(cantidad_clams)
            }
            success, msg = guardar_cosecha(data)
            if success:
                st.success(msg)
                st.balloons()
                st.session_state.clams_value = 0.0
                st.session_state.cajas_calculadas = 0.0
            else:
                st.error(msg)

def mostrar_control_asistencia():
    st.header("🕐 Control de Asistencia")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📱 Registrar Asistencia", "📊 Resumen del Día", "📋 Historial", "💤 Registrar Descanso", "⚠️ Incidencias"])
    
    with tab1:
        st.subheader("Registro de Asistencia")
        tab_scan, tab_manual = st.tabs(["📷 Escanear QR", "📝 Registrar Manual"])
        
        with tab_scan:
            escanear_qr_con_camara(tipo_evento="asistencia", mostrar_invernadero=True)
        
        with tab_manual:
            trabajadores = get_all_workers()
            if not trabajadores.empty:
                trabajador_seleccionado = st.selectbox(
                    "Seleccionar trabajador:", 
                    trabajadores.apply(lambda x: f"{x['id']} - {x['nombre']} {x['apellido_paterno']}", axis=1),
                    key="trabajador_asistencia_manual"
                )
                trabajador_id = int(trabajador_seleccionado.split(' - ')[0]) if trabajador_seleccionado else None
            else:
                trabajador_id = None
            
            invernaderos = get_invernaderos()
            if invernaderos:
                invernadero = st.selectbox(
                    "Invernadero:", 
                    invernaderos, 
                    format_func=lambda x: f"{x[1]} - {x[2]}",
                    key="invernadero_asistencia_manual"
                )
                invernadero_id = invernadero[0]
            else:
                invernadero_id = None
            
            tipo_evento = st.selectbox(
                "Tipo de Evento:", 
                ["entrada_invernadero", "salida_comer", "regreso_comida", "salida_invernadero"],
                format_func=lambda x: {'entrada_invernadero': '🚪 Entrada', 'salida_comer': '🍽️ Salida a Comer',
                                        'regreso_comida': '✅ Regreso de Comida', 'salida_invernadero': '🚪 Salida'}[x],
                key="tipo_evento_asistencia_manual"
            )
            
            if st.button("✅ Registrar Evento", type="primary", use_container_width=True, key="btn_registrar_evento_manual"):
                if not trabajador_id:
                    st.error("Seleccione un trabajador")
                elif tipo_evento == 'entrada_invernadero' and not invernadero_id:
                    st.error("Seleccione un invernadero")
                else:
                    success, msg = registrar_evento_asistencia(trabajador_id, invernadero_id if tipo_evento == 'entrada_invernadero' else None, tipo_evento)
                    if success:
                        st.success(msg)
                        st.balloons()
                    else:
                        st.error(msg)
    
    with tab2:
        st.subheader("Resumen de Asistencia del Día")
        fecha_resumen = st.date_input("Seleccionar fecha:", datetime.now().date(), key="fecha_resumen_asist")
        
        if st.button("Actualizar Resumen", key="btn_resumen_asist", use_container_width=True):
            df_resumen = get_resumen_asistencia_dia(fecha_resumen)
            if not df_resumen.empty:
                col1, col2, col3, col4, col5, col6 = st.columns(6)
                with col1: st.metric("Total", len(df_resumen))
                with col2: st.metric("Presentes", len(df_resumen[df_resumen['estado_actual'].str.contains('Finalizado|En invernadero|En comida', na=False)]))
                with col3: st.metric("Faltas", len(df_resumen[df_resumen['estado_actual'] == 'Falta']))
                with col4: st.metric("Descansos", len(df_resumen[df_resumen['estado_actual'] == 'Descanso']))
                with col5: st.metric("En Invernadero", len(df_resumen[df_resumen['estado_actual'] == 'En invernadero']))
                with col6: st.metric("Incidencias", len(df_resumen[df_resumen['estado_actual'].str.contains('Incidencia:', na=False)]))
                
                st.dataframe(df_resumen[['trabajador', 'hora_entrada', 'hora_salida_comida', 'hora_entrada_comida', 'hora_salida', 'invernadero', 'estado_actual']], 
                            use_container_width=True)
                
                output = export_to_excel(df_resumen, f"Asistencia_{fecha_resumen}")
                st.download_button("📥 Exportar a Excel", data=output, file_name=f"asistencia_{fecha_resumen}.xlsx")
            else:
                st.info("No hay registros para esta fecha")
    
    with tab3:
        st.subheader("Historial de Asistencia")
        col1, col2, col3 = st.columns(3)
        with col1:
            trabajadores_list = get_all_workers()
            trabajadores_opciones = [("", "Todos")] + [(row['id'], f"{row['nombre']} {row['apellido_paterno']}") for _, row in trabajadores_list.iterrows()]
            trabajador_seleccionado = st.selectbox(
                "Filtrar por trabajador:", 
                trabajadores_opciones, 
                format_func=lambda x: x[1] if isinstance(x, tuple) else x,
                key="hist_trabajador_asist"
            )
        with col2:
            fecha_inicio = st.date_input("Fecha inicio:", datetime.now().date() - timedelta(days=30), key="hist_inicio_asist")
        with col3:
            fecha_fin = st.date_input("Fecha fin:", datetime.now().date(), key="hist_fin_asist")
        
        if st.button("🔍 Buscar Registros", key="btn_buscar_historial", use_container_width=True):
            filtros = {}
            if trabajador_seleccionado and trabajador_seleccionado[0]:
                filtros['trabajador_id'] = trabajador_seleccionado[0]
            filtros['fecha_inicio'] = fecha_inicio
            filtros['fecha_fin'] = fecha_fin
            df_historial = get_registros_asistencia(filtros)
            if not df_historial.empty:
                st.dataframe(df_historial, use_container_width=True)
                output = export_to_excel(df_historial, "Historial_Asistencia")
                st.download_button("📥 Exportar Historial", data=output, file_name=f"historial_asistencia_{datetime.now().date()}.xlsx")
            else:
                st.info("No se encontraron registros")
    
    with tab4:
        st.subheader("💤 Registrar Descanso")
        col1, col2 = st.columns(2)
        with col1:
            trabajadores = get_all_workers()
            trabajador_seleccionado = st.selectbox(
                "Seleccionar trabajador:", 
                trabajadores.apply(lambda x: f"{x['id']} - {x['nombre']} {x['apellido_paterno']}", axis=1) if not trabajadores.empty else [],
                key="descanso_trabajador_select"
            )
            trabajador_id = int(trabajador_seleccionado.split(' - ')[0]) if trabajador_seleccionado else None
        with col2:
            fecha_descanso = st.date_input("Fecha de descanso:", datetime.now().date(), key="fecha_descanso")
        
        tipo_descanso = st.selectbox(
            "Tipo de Descanso:", 
            ["Descanso", "Vacaciones", "Permiso", "Enfermedad", "Capacitación", "Otro"],
            key="tipo_descanso_select"
        )
        observaciones = st.text_area("Observaciones:", key="obs_descanso")
        
        if st.button("✅ Registrar Descanso", key="btn_registrar_descanso", type="primary", use_container_width=True):
            if trabajador_id:
                success, msg = registrar_descanso(trabajador_id, fecha_descanso, tipo_descanso, observaciones)
                if success:
                    st.success(msg)
                    st.balloons()
                else:
                    st.error(msg)
            else:
                st.error("Seleccione un trabajador")
    
    with tab5:
        st.subheader("⚠️ Registro de Incidencias")
        
        st.markdown("""
        <div style="background-color: #fff3cd; padding: 15px; border-radius: 10px; margin-bottom: 20px;">
        <strong>📌 Tipos de Incidencias:</strong><br>
        • <strong>Enfermedad</strong> - Incapacidad médica o enfermedad<br>
        • <strong>Permiso Justificado</strong> - Permiso con justificación (documento, comprobante)<br>
        • <strong>Permiso Injustificado</strong> - Permiso sin justificación<br>
        • <strong>Retardo</strong> - Llegada tarde al trabajo<br>
        • <strong>Falta Justificada</strong> - Falta con justificación<br>
        • <strong>Falta Injustificada</strong> - Falta sin justificación<br>
        • <strong>Otra</strong> - Otro tipo de incidencia
        </div>
        """, unsafe_allow_html=True)
        
        with st.form("form_incidencia"):
            col1, col2 = st.columns(2)
            with col1:
                trabajadores = get_all_workers()
                if not trabajadores.empty:
                    trabajador_incidencia = st.selectbox(
                        "👤 Seleccionar trabajador *", 
                        trabajadores.apply(lambda x: f"{x['id']} - {x['nombre']} {x['apellido_paterno']} ({x['puesto']})", axis=1),
                        key="incidencia_trabajador_select"
                    )
                    trabajador_id = int(trabajador_incidencia.split(' - ')[0]) if trabajador_incidencia else None
                else:
                    trabajador_id = None
                    st.warning("No hay trabajadores registrados")
            
            with col2:
                fecha_incidencia = st.date_input("📅 Fecha de incidencia *", datetime.now().date(), key="fecha_incidencia")
            
            tipo_incidencia = st.selectbox(
                "📌 Tipo de Incidencia *", 
                ["Enfermedad", "Permiso Justificado", "Permiso Injustificado", "Retardo", "Falta Justificada", "Falta Injustificada", "Otra"],
                key="tipo_incidencia_select"
            )
            
            subtipo = None
            horas_afectadas = 0.0
            
            if tipo_incidencia == "Enfermedad":
                subtipo = st.selectbox(
                    "🩺 Tipo de enfermedad", 
                    ["General", "Accidente", "Incapacidad", "Consulta médica", "Covid-19", "Gripe", "Gastrointestinal", "Otro"],
                    key="subtipo_enfermedad"
                )
                horas_afectadas = st.number_input("⏱️ Horas afectadas", min_value=0.0, max_value=24.0, step=0.5, key="horas_afectadas")
            
            elif tipo_incidencia in ["Permiso Justificado", "Permiso Injustificado"]:
                horas_afectadas = st.number_input("⏱️ Horas afectadas", min_value=0.0, max_value=24.0, step=0.5, key="horas_afectadas")
                if tipo_incidencia == "Permiso Justificado":
                    subtipo = st.selectbox("📄 Tipo de permiso", ["Personal", "Trámite", "Familiar", "Cita médica", "Otro"], key="subtipo_permiso")
            
            elif tipo_incidencia == "Retardo":
                minutos_retardo = st.number_input("⏰ Minutos de retardo", min_value=0, max_value=480, step=5, key="minutos_retardo")
                horas_afectadas = minutos_retardo / 60.0
                subtipo = f"{minutos_retardo} minutos"
            
            elif tipo_incidencia in ["Falta Justificada", "Falta Injustificada"]:
                horas_afectadas = st.number_input("⏱️ Horas afectadas (día completo = 8)", min_value=0.0, max_value=24.0, step=0.5, key="horas_afectadas", value=8.0)
            
            justificada = st.checkbox("📋 ¿Incidencia justificada?", key="incidencia_justificada")
            observaciones = st.text_area("📝 Observaciones", placeholder="Detalles adicionales sobre la incidencia...", key="obs_incidencia")
            registrado_por = st.text_input("✍️ Registrado por", placeholder="Nombre de quien registra la incidencia", key="registrado_por")
            
            if st.form_submit_button("✅ Registrar Incidencia", type="primary", use_container_width=True):
                if not trabajador_id:
                    st.error("❌ Seleccione un trabajador")
                elif not registrado_por:
                    st.error("❌ Ingrese quién registra la incidencia")
                else:
                    success, msg = registrar_incidencia(
                        trabajador_id, fecha_incidencia, tipo_incidencia, subtipo,
                        horas_afectadas, justificada, observaciones, registrado_por
                    )
                    if success:
                        st.success(msg)
                        st.balloons()
                        st.rerun()
                    else:
                        st.error(msg)
        
        st.markdown("---")
        st.subheader("📊 Estadísticas de Incidencias")
        
        col1, col2 = st.columns(2)
        with col1:
            fecha_inc_inicio = st.date_input("Fecha inicio:", datetime.now().date() - timedelta(days=30), key="inc_inicio")
        with col2:
            fecha_inc_fin = st.date_input("Fecha fin:", datetime.now().date(), key="inc_fin")
        
        resumen_inc = get_resumen_incidencias(fecha_inc_inicio, fecha_inc_fin)
        
        if not resumen_inc['resumen_tipo'].empty:
            col1, col2 = st.columns(2)
            with col1:
                fig = px.pie(resumen_inc['resumen_tipo'], values='cantidad', names='tipo_incidencia',
                            title='Distribución por Tipo de Incidencia',
                            color_discrete_sequence=px.colors.qualitative.Set2)
                fig.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                fig = px.bar(resumen_inc['resumen_tipo'], x='tipo_incidencia', y='cantidad',
                            title='Cantidad de Incidencias por Tipo',
                            color='tipo_incidencia',
                            text='cantidad')
                fig.update_traces(texttemplate='%{text}', textposition='outside')
                fig.update_layout(showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")
        st.subheader("📋 Historial de Incidencias")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            fecha_hist_inc_inicio = st.date_input("Fecha inicio histórico:", fecha_inc_inicio, key="hist_inc_inicio")
        with col2:
            fecha_hist_inc_fin = st.date_input("Fecha fin histórico:", fecha_inc_fin, key="hist_inc_fin")
        with col3:
            trabajadores = get_all_workers()
            trabajadores_inc = [("", "Todos")] + [(row['id'], f"{row['nombre']} {row['apellido_paterno']}") 
                                                   for _, row in trabajadores.iterrows()] if not trabajadores.empty else [("", "Todos")]
            filtro_trabajador_inc = st.selectbox(
                "Filtrar por trabajador:",
                trabajadores_inc,
                format_func=lambda x: x[1] if isinstance(x, tuple) else x,
                key="filtro_trabajador_inc"
            )
        
        trabajador_id_filtro = filtro_trabajador_inc[0] if filtro_trabajador_inc and filtro_trabajador_inc[0] else None
        
        incidencias = get_incidencias(fecha_hist_inc_inicio, fecha_hist_inc_fin, trabajador_id_filtro)
        
        if not incidencias.empty:
            incidencias_display = incidencias.copy()
            incidencias_display['fecha'] = pd.to_datetime(incidencias_display['fecha']).dt.strftime('%d/%m/%Y')
            incidencias_display['justificada'] = incidencias_display['justificada'].map({1: '✅ Sí', 0: '❌ No'})
            
            st.dataframe(
                incidencias_display[['fecha', 'trabajador', 'tipo_incidencia', 'subtipo', 
                                     'horas_afectadas', 'justificada', 'observaciones', 'registrado_por']],
                use_container_width=True,
                column_config={
                    "fecha": "Fecha",
                    "trabajador": "Trabajador",
                    "tipo_incidencia": "Tipo",
                    "subtipo": "Subtipo",
                    "horas_afectadas": "Horas",
                    "justificada": "Justificada",
                    "observaciones": "Observaciones",
                    "registrado_por": "Registrado por"
                }
            )
            
            output = export_to_excel(incidencias, "Incidencias")
            st.download_button(
                "📥 Exportar Incidencias a Excel",
                data=output,
                file_name=f"incidencias_{datetime.now().date()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("No hay registros de incidencias en el período seleccionado")

def mostrar_avance_cosecha():
    st.header("📊 Registro de Avance de Cosecha")
    
    st.markdown("""
    <div style="background-color: #e8f5e9; padding: 15px; border-radius: 10px; margin-bottom: 20px;">
        <strong>📌 Información:</strong><br>
        • Invernaderos 1 al 8: <strong>40 líneas</strong> cada uno<br>
        • Invernaderos 9 al 11: <strong>36 líneas</strong> cada uno<br>
        • Cada día comienza desde 0 líneas cosechadas<br>
        • Se pueden registrar múltiples avances durante el día<br>
        • El porcentaje se calcula automáticamente sobre el total del día
    </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["📝 Registrar Avance", "📊 Historial de Avance"])
    
    with tab1:
        st.subheader("Registrar Avance Diario")
        
        fecha_actual = datetime.now()
        fecha_formateada = fecha_actual.strftime("%Y/%m/%d")
        hora_actual = fecha_actual.strftime("%H:%M")
        semana_actual = fecha_actual.isocalendar()[1]
        
        col_fecha, col_hora, col_semana = st.columns(3)
        
        with col_fecha:
            st.markdown(f"""
            <div class="date-card">
                <div style="font-size: 12px; color: rgba(255,255,255,0.8);">📅 FECHA DEL REGISTRO</div>
                <div style="font-size: 24px; font-weight: bold; color: white;">{fecha_formateada}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col_hora:
            st.markdown(f"""
            <div class="time-card">
                <div style="font-size: 12px; color: rgba(255,255,255,0.8);">⏰ HORA DEL REGISTRO</div>
                <div style="font-size: 24px; font-weight: bold; color: white;">{hora_actual}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col_semana:
            st.markdown(f"""
            <div class="week-card">
                <div style="font-size: 12px; color: rgba(255,255,255,0.8);">📆 SEMANA</div>
                <div style="font-size: 24px; font-weight: bold; color: white;">{semana_actual}</div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            invernaderos = get_invernaderos()
            if invernaderos:
                invernadero_seleccionado = st.selectbox(
                    "Seleccionar Invernadero *",
                    invernaderos,
                    format_func=lambda x: f"{x[1]} - {x[2]}",
                    key="invernadero_avance"
                )
                invernadero_id = invernadero_seleccionado[0]
                invernadero_nombre = invernadero_seleccionado[1]
                
                lineas_totales = get_lineas_totales_por_invernadero(invernadero_id, invernadero_nombre)
                st.info(f"📏 Total de líneas en {invernadero_nombre}: {lineas_totales}")
            else:
                st.error("No hay invernaderos registrados")
                invernadero_id = None
                invernadero_nombre = None
                lineas_totales = 0
        
        with col2:
            supervisor = st.text_input("Nombre del Supervisor *", placeholder="Ingrese su nombre", key="supervisor_avance")
        
        with col3:
            turno = st.selectbox(
                "Turno *",
                ["Matutino", "Vespertino", "Nocturno"],
                key="turno_avance"
            )
        
        st.markdown("---")
        
        if invernadero_id:
            ultimo_avance = get_ultimo_avance_dia(invernadero_id)
            
            if ultimo_avance:
                st.info(f"""
                📊 **Avance actual del día ({invernadero_nombre}):**
                - Líneas cosechadas: **{ultimo_avance['lineas_cosechadas']}** de {lineas_totales}
                - Porcentaje: **{ultimo_avance['porcentaje']:.1f}%**
                - Última actualización: **{ultimo_avance['hora']}** (Turno: {ultimo_avance['turno']})
                """)
                
                lineas_restantes = lineas_totales - ultimo_avance['lineas_cosechadas']
                if lineas_restantes > 0:
                    st.warning(f"💡 Faltan {lineas_restantes} líneas por cosechar para completar el día")
            else:
                st.success(f"✨ Primer registro del día para {invernadero_nombre}. ¡Comienza desde 0!")
        
        col1, col2 = st.columns(2)
        
        with col1:
            valor_inicial = 0
            if invernadero_id and ultimo_avance:
                valor_inicial = ultimo_avance['lineas_cosechadas']
            
            lineas_cosechadas = st.number_input(
                "Líneas Cosechadas *",
                min_value=0,
                max_value=lineas_totales,
                value=valor_inicial,
                step=1,
                key="lineas_cosechadas"
            )
        
        with col2:
            if lineas_totales > 0:
                porcentaje_calculado = (lineas_cosechadas / lineas_totales) * 100
                st.metric("Porcentaje de Avance", f"{porcentaje_calculado:.1f}%")
                
                if ultimo_avance and lineas_cosechadas < ultimo_avance['lineas_cosechadas']:
                    st.warning("⚠️ El valor ingresado es menor que el registro anterior. ¿Es correcto?")
        
        observaciones = st.text_area("Observaciones (opcional)", placeholder="Notas adicionales sobre el avance...", key="obs_avance")
        
        if st.button("✅ Registrar Avance", type="primary", use_container_width=True, key="btn_registrar_avance"):
            if not invernadero_id:
                st.error("❌ Seleccione un invernadero")
            elif not supervisor:
                st.error("❌ Ingrese el nombre del supervisor")
            elif lineas_cosechadas <= 0:
                st.error("❌ Ingrese la cantidad de líneas cosechadas")
            elif ultimo_avance and lineas_cosechadas < ultimo_avance['lineas_cosechadas']:
                st.error("❌ El avance no puede disminuir. Si hubo un error, use el historial para corregir.")
            else:
                success, msg = registrar_avance_cosecha(
                    invernadero_id,
                    invernadero_nombre,
                    lineas_cosechadas,
                    supervisor,
                    observaciones,
                    turno
                )
                if success:
                    st.success(msg)
                    st.balloons()
                    st.rerun()
                else:
                    st.error(msg)
    
    with tab2:
        st.subheader("Historial de Avance de Cosecha")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            fecha_hist_inicio = st.date_input("Fecha inicio:", datetime.now().date() - timedelta(days=30), key="avance_hist_inicio")
        with col2:
            fecha_hist_fin = st.date_input("Fecha fin:", datetime.now().date(), key="avance_hist_fin")
        with col3:
            turno_filtro = st.selectbox("Filtrar por turno:", ["Todos", "Matutino", "Vespertino", "Nocturno"], key="turno_filtro_hist")
        
        turno_param = None if turno_filtro == "Todos" else turno_filtro
        
        df_avance = get_avance_historico_por_dia(fecha_hist_inicio, fecha_hist_fin, turno=turno_param)
        
        if not df_avance.empty:
            df_display = df_avance.copy()
            df_display['fecha'] = pd.to_datetime(df_display['fecha']).dt.strftime('%d/%m/%Y')
            df_display['porcentaje'] = df_display['porcentaje'].map(lambda x: f"{x:.1f}%")
            
            st.dataframe(
                df_display[['fecha', 'hora', 'turno', 'invernadero_nombre', 'lineas_cosechadas', 'lineas_totales', 'porcentaje', 'supervisor', 'observaciones']],
                use_container_width=True,
                column_config={
                    "fecha": "Fecha",
                    "hora": "Hora",
                    "turno": "Turno",
                    "invernadero_nombre": "Invernadero",
                    "lineas_cosechadas": "Líneas Cosechadas",
                    "lineas_totales": "Líneas Totales",
                    "porcentaje": "Porcentaje",
                    "supervisor": "Supervisor",
                    "observaciones": "Observaciones"
                }
            )
            
            output = export_to_excel(df_avance, "Avance_Cosecha_Historico")
            st.download_button(
                "📥 Exportar Historial a Excel",
                data=output,
                file_name=f"avance_cosecha_historico_{datetime.now().date()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
            if not df_avance.empty:
                st.subheader("📈 Evolución del Avance por Día")
                fig = px.line(df_avance, x='fecha', y='porcentaje', color='invernadero_nombre',
                             title='Evolución del Porcentaje de Avance por Día',
                             labels={'fecha': 'Fecha', 'porcentaje': 'Porcentaje (%)', 'invernadero_nombre': 'Invernadero'},
                             markers=True)
                fig.update_layout(plot_bgcolor='white', height=500)
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay registros de avance en el período seleccionado")

def mostrar_envios_enfriado():
    st.header("❄️ Gestión de Envíos a Enfriado")
    
    tab1, tab2, tab3 = st.tabs(["📦 Registrar Envío", "📊 Dashboard Envíos", "📋 Historial"])
    
    with tab1:
        st.subheader("Registrar Envío de Cajas a Enfriado")
        
        fecha_actual = datetime.now()
        hora_actual = fecha_actual.strftime("%H:%M")
        fecha_formateada = fecha_actual.strftime("%Y/%m/%d")
        semana_actual = fecha_actual.isocalendar()[1]
        
        col_fecha, col_hora, col_semana = st.columns(3)
        
        with col_fecha:
            st.markdown(f"""
            <div class="date-card">
                <div style="font-size: 12px; color: rgba(255,255,255,0.8);">📅 FECHA DEL ENVÍO</div>
                <div style="font-size: 24px; font-weight: bold; color: white;">{fecha_formateada}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col_hora:
            st.markdown(f"""
            <div class="time-card">
                <div style="font-size: 12px; color: rgba(255,255,255,0.8);">⏰ HORA DEL ENVÍO</div>
                <div style="font-size: 24px; font-weight: bold; color: white;">{hora_actual}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col_semana:
            st.markdown(f"""
            <div class="week-card">
                <div style="font-size: 12px; color: rgba(255,255,255,0.8);">📆 SEMANA</div>
                <div style="font-size: 24px; font-weight: bold; color: white;">{semana_actual}</div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        
        with col1:
            invernaderos = get_invernaderos()
            if invernaderos:
                invernadero_seleccionado = st.selectbox(
                    "🏭 Invernadero de origen:",
                    invernaderos,
                    format_func=lambda x: f"{x[1]} - {x[2]}",
                    key="invernadero_envio"
                )
                invernadero_id = invernadero_seleccionado[0]
            else:
                st.error("No hay invernaderos registrados")
                invernadero_id = None
        
        with col2:
            if invernadero_id:
                detalle_cajas = get_detalle_cajas_por_invernadero_presentacion(invernadero_id)
                total_cajas = detalle_cajas['6 oz'] + detalle_cajas['12 oz']
                
                st.markdown(f"""
                <div style="background-color: #e8f4fd; padding: 15px; border-radius: 10px; margin-bottom: 10px;">
                    <h4 style="margin: 0 0 10px 0;">📦 Inventario en {invernadero_seleccionado[1]}</h4>
                    <p style="margin: 5px 0;"><strong>Total cajas disponibles:</strong> {total_cajas:.0f}</p>
                    <hr style="margin: 10px 0;">
                    <p style="margin: 5px 0;">🍓 <strong>Cajas 6 oz:</strong> {detalle_cajas['6 oz']:.0f} cajas</p>
                    <p style="margin: 5px 0;">🍓 <strong>Cajas 12 oz:</strong> {detalle_cajas['12 oz']:.0f} cajas</p>
                </div>
                """, unsafe_allow_html=True)
                
                if total_cajas == 0:
                    st.warning("⚠️ No hay cajas disponibles en este invernadero")
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("👤 Supervisor que entrega las cajas")
            trabajadores = get_all_workers()
            if not trabajadores.empty:
                supervisores = trabajadores[trabajadores['puesto'].str.contains('Supervisor', case=False, na=False)]
                if not supervisores.empty:
                    supervisor_envia = st.selectbox(
                        "Supervisor:",
                        supervisores.apply(lambda x: f"{x['id']} - {x['nombre']} {x['apellido_paterno']} ({x['puesto']})", axis=1),
                        key="supervisor_envia"
                    )
                    supervisor_envia_id = int(supervisor_envia.split(' - ')[0]) if supervisor_envia else None
                else:
                    st.warning("No hay supervisores registrados. Agrega supervisores en la sección de trabajadores.")
                    supervisor_envia_id = None
            else:
                supervisor_envia_id = None
        
        with col2:
            st.markdown("---")
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        
        with col1:
            tipo_envio = st.selectbox(
                "📦 Tipo de Envío:",
                ["Nacional", "Exportación"],
                help="Selecciona si las cajas son para mercado nacional o exportación",
                key="tipo_envio_select"
            )
        
        with col2:
            presentacion = st.selectbox(
                "📏 Presentación:",
                ["6 oz", "12 oz"],
                help="Tamaño de las cajas",
                key="presentacion_envio"
            )
        
        cantidad_cajas = st.number_input("📊 Cantidad de Cajas a enviar:", min_value=0.0, step=1.0, key="cantidad_envio")
        lote = st.text_input("🏷️ Número de Lote (opcional):", placeholder="Ej: L-2024-001", key="lote_envio")
        observaciones = st.text_area("📝 Observaciones:", placeholder="Ej: Calidad premium, primera selección, etc.", key="obs_envio")
        
        if invernadero_id and cantidad_cajas > 0:
            detalle_cajas = get_detalle_cajas_por_invernadero_presentacion(invernadero_id)
            cajas_disponibles_por_tipo = detalle_cajas.get(presentacion, 0)
            
            if cantidad_cajas > cajas_disponibles_por_tipo:
                st.warning(f"⚠️ Solo hay {cajas_disponibles_por_tipo:.0f} cajas de {presentacion} disponibles en este invernadero")
        
        if st.button("✅ Registrar Envío a Enfriado", type="primary", use_container_width=True, key="btn_registrar_envio"):
            if not invernadero_id:
                st.error("Seleccione un invernadero de origen")
            elif not supervisor_envia_id:
                st.error("Seleccione el supervisor que entrega las cajas")
            elif cantidad_cajas <= 0:
                st.error("Ingrese una cantidad válida de cajas")
            else:
                detalle_cajas = get_detalle_cajas_por_invernadero_presentacion(invernadero_id)
                cajas_disponibles_por_tipo = detalle_cajas.get(presentacion, 0)
                
                if cantidad_cajas > cajas_disponibles_por_tipo:
                    st.error(f"❌ No hay suficientes cajas de {presentacion}. Disponibles: {cajas_disponibles_por_tipo:.0f}")
                else:
                    success, msg = registrar_envio_enfriado(
                        invernadero_id, cantidad_cajas, supervisor_envia_id, 
                        tipo_envio, presentacion, lote, observaciones
                    )
                    if success:
                        st.success(msg)
                        st.balloons()
                        st.rerun()
                    else:
                        st.error(msg)
    
    with tab2:
        st.subheader("📊 Dashboard de Envíos")
        col1, col2 = st.columns(2)
        with col1:
            fecha_inicio = st.date_input("Fecha inicio:", datetime.now().date() - timedelta(days=30), key="envio_inicio")
        with col2:
            fecha_fin = st.date_input("Fecha fin:", datetime.now().date(), key="envio_fin")
        
        stats_envios = get_stats_envios_avanzado(fecha_inicio, fecha_fin)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1: st.metric("📦 Total Cajas", f"{stats_envios['total_cajas']:,.0f}")
        with col2: st.metric("🚚 Total Envíos", len(stats_envios['envios_diarios']) if not stats_envios['envios_diarios'].empty else 0)
        with col3: st.metric("📊 Promedio/Día", f"{stats_envios['total_cajas'] / max(len(stats_envios['envios_diarios']), 1):.1f}")
        with col4: st.metric("🏆 Top Invernadero", stats_envios['envios_por_invernadero'].iloc[0]['invernadero'] if not stats_envios['envios_por_invernadero'].empty else "N/A")
        
        if not stats_envios['envios_diarios'].empty:
            fig = px.bar(stats_envios['envios_diarios'], x='fecha', y='cajas', title='Envíos Diarios')
            st.plotly_chart(fig, use_container_width=True)
        
        st.subheader("📊 Resumen de Cajas por Invernadero")
        df_resumen = get_resumen_cajas_por_invernadero()
        if not df_resumen.empty and len(df_resumen) > 0:
            st.dataframe(df_resumen, use_container_width=True)
            
            fig = go.Figure()
            fig.add_trace(go.Bar(name='Cosechadas', x=df_resumen['invernadero'], y=df_resumen['cosechadas'], marker_color='#3498db'))
            fig.add_trace(go.Bar(name='Enviadas', x=df_resumen['invernadero'], y=df_resumen['enviadas'], marker_color='#e74c3c'))
            fig.add_trace(go.Bar(name='Disponibles', x=df_resumen['invernadero'], y=df_resumen['disponibles'], marker_color='#2ecc71'))
            
            fig.update_layout(
                title='Cajas por Invernadero',
                xaxis_title='Invernadero',
                yaxis_title='Cajas',
                barmode='group',
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)'
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay datos de cajas por invernadero")
        
        st.subheader("📋 Detalle de Cajas por Invernadero")
        invernaderos = get_invernaderos()
        if invernaderos:
            invernadero_detalle = st.selectbox(
                "Seleccione un invernadero para ver detalle:",
                invernaderos,
                format_func=lambda x: f"{x[1]} - {x[2]}",
                key="invernadero_detalle"
            )
            inv_id_detalle = invernadero_detalle[0]
            inv_nombre_detalle = invernadero_detalle[1]
            
            detalle_cajas = get_detalle_cajas_por_invernadero_presentacion(inv_id_detalle)
            st.metric(f"Cajas disponibles en {inv_nombre_detalle}", f"{detalle_cajas['6 oz'] + detalle_cajas['12 oz']:.0f}")
            st.write(f"🍓 6 oz: {detalle_cajas['6 oz']:.0f} cajas")
            st.write(f"🍓 12 oz: {detalle_cajas['12 oz']:.0f} cajas")
            
            cosechas_detalle, envios_detalle = get_detalle_cajas_por_invernadero(inv_id_detalle)
            
            with st.expander("📦 Cosechas registradas en este invernadero", expanded=True):
                if not cosechas_detalle.empty:
                    st.dataframe(cosechas_detalle[['fecha', 'presentacion', 'cantidad_clams', 'numero_cajas', 'cajas_enviadas', 'disponibles']], 
                                 use_container_width=True,
                                 column_config={
                                     "fecha": "Fecha",
                                     "presentacion": "Presentación",
                                     "cantidad_clams": "Clams",
                                     "numero_cajas": "Cajas Cosechadas",
                                     "cajas_enviadas": "Cajas Enviadas",
                                     "disponibles": "Cajas Disponibles"
                                 })
                else:
                    st.info("No hay cosechas registradas en este invernadero")
            
            with st.expander("🚚 Envíos realizados desde este invernadero", expanded=True):
                if not envios_detalle.empty:
                    columnas_disponibles = envios_detalle.columns.tolist()
                    columnas_a_mostrar = ['fecha', 'hora', 'tipo_envio', 'presentacion', 'cantidad_cajas', 'supervisor']
                    if 'lote' in columnas_disponibles:
                        columnas_a_mostrar.append('lote')
                    if 'observaciones' in columnas_disponibles:
                        columnas_a_mostrar.append('observaciones')
                    
                    st.dataframe(envios_detalle[columnas_a_mostrar],
                                 use_container_width=True,
                                 column_config={
                                     "fecha": "Fecha",
                                     "hora": "Hora",
                                     "tipo_envio": "Tipo",
                                     "presentacion": "Presentación",
                                     "cantidad_cajas": "Cajas",
                                     "supervisor": "Supervisor",
                                     "lote": "Lote",
                                     "observaciones": "Observaciones"
                                 })
                else:
                    st.info("No hay envíos registrados desde este invernadero")
        else:
            st.info("No hay invernaderos registrados")
    
    with tab3:
        st.subheader("📋 Historial de Envíos")
        col1, col2, col3 = st.columns(3)
        with col1:
            fecha_hist_inicio = st.date_input("Fecha inicio:", datetime.now().date() - timedelta(days=30), key="hist_inicio")
        with col2:
            fecha_hist_fin = st.date_input("Fecha fin:", datetime.now().date(), key="hist_fin")
        with col3:
            invernaderos_filtro = [("", "Todos")] + [(id_inv, nombre) for id_inv, nombre, _ in get_invernaderos()]
            invernadero_filtro = st.selectbox("Filtrar por invernadero:", invernaderos_filtro, format_func=lambda x: x[1] if isinstance(x, tuple) else x, key="invernadero_historial")
        
        invernadero_id_filtro = invernadero_filtro[0] if invernadero_filtro and invernadero_filtro[0] else None
        envios = get_envios_enfriado(fecha_hist_inicio, fecha_hist_fin, invernadero_id_filtro)
        
        if not envios.empty:
            st.dataframe(envios, use_container_width=True)
            output = export_to_excel(envios, "Envios_Enfriado")
            st.download_button("📥 Exportar a Excel", data=output, file_name=f"envios_enfriado_{datetime.now().date()}.xlsx")
        else:
            st.info("No hay envíos registrados")

def mostrar_gestion_merma():
    st.header("🗑️ Gestión de Merma")
    
    tab1, tab2, tab3 = st.tabs(["📝 Registrar Merma", "📊 Dashboard Merma", "📋 Historial"])
    
    with tab1:
        st.subheader("Registrar Merma")
        
        fecha_actual = datetime.now()
        fecha_formateada = fecha_actual.strftime("%Y/%m/%d")
        hora_actual = fecha_actual.strftime("%H:%M")
        semana_actual = fecha_actual.isocalendar()[1]
        
        col_fecha, col_hora, col_semana = st.columns(3)
        
        with col_fecha:
            st.markdown(f"""
            <div class="date-card">
                <div style="font-size: 12px; color: rgba(255,255,255,0.8);">📅 FECHA DEL REGISTRO</div>
                <div style="font-size: 24px; font-weight: bold; color: white;">{fecha_formateada}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col_hora:
            st.markdown(f"""
            <div class="time-card">
                <div style="font-size: 12px; color: rgba(255,255,255,0.8);">⏰ HORA DEL REGISTRO</div>
                <div style="font-size: 24px; font-weight: bold; color: white;">{hora_actual}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col_semana:
            st.markdown(f"""
            <div class="week-card">
                <div style="font-size: 12px; color: rgba(255,255,255,0.8);">📆 SEMANA</div>
                <div style="font-size: 24px; font-weight: bold; color: white;">{semana_actual}</div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        with st.form("form_merma"):
            col1, col2 = st.columns(2)
            with col1:
                invernaderos = get_invernaderos()
                if invernaderos:
                    invernadero = st.selectbox("Invernadero *", invernaderos, format_func=lambda x: f"{x[1]} - {x[2]}", key="invernadero_merma")
                    invernadero_id = invernadero[0]
                else:
                    invernadero_id = None
            with col2:
                supervisor_nombre = st.text_input("Nombre del Supervisor *", key="supervisor_merma")
            
            kilos_merma = st.number_input("Kilos de Merma *", min_value=0.0, step=0.5, key="kilos_merma")
            tipo_merma = st.selectbox("Tipo de Merma", ["Seleccionar...", "Fruta dañada", "Fruta sobremadura", "Fruta con defectos", "Contaminación", "Manejo inadecuado", "Temperatura", "Plagas", "Otra"], key="tipo_merma")
            observaciones = st.text_area("Observaciones", key="obs_merma")
            registrado_por = st.text_input("Registrado por *", key="registrado_por_merma")
            
            if st.form_submit_button("✅ Registrar Merma", type="primary", use_container_width=True):
                if invernadero_id and supervisor_nombre and kilos_merma > 0 and tipo_merma != "Seleccionar..." and registrado_por:
                    success, msg = registrar_merma(invernadero_id, supervisor_nombre, kilos_merma, tipo_merma, observaciones, registrado_por)
                    if success:
                        st.success(msg)
                        st.balloons()
                    else:
                        st.error(msg)
                else:
                    st.error("Complete todos los campos")
    
    with tab2:
        st.subheader("Dashboard Merma")
        col1, col2 = st.columns(2)
        with col1:
            fecha_inicio = st.date_input("Fecha inicio:", datetime.now().date() - timedelta(days=30), key="merma_inicio")
        with col2:
            fecha_fin = st.date_input("Fecha fin:", datetime.now().date(), key="merma_fin")
        
        stats_merma = get_stats_merma(fecha_inicio, fecha_fin)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1: st.metric("🗑️ Total Kilos", f"{stats_merma['total_merma']:,.2f} kg")
        with col2: st.metric("📊 Promedio/Día", f"{stats_merma['total_merma'] / max(len(stats_merma['merma_diaria']), 1):.1f} kg")
        with col3: st.metric("📝 Registros", len(stats_merma['merma_diaria']) if not stats_merma['merma_diaria'].empty else 0)
        with col4: st.metric("🏆 Mayor Merma", stats_merma['merma_por_invernadero'].iloc[0]['invernadero_nombre'] if not stats_merma['merma_por_invernadero'].empty else "N/A")
        
        if not stats_merma['merma_diaria'].empty:
            fig = px.bar(stats_merma['merma_diaria'], x='fecha', y='kilos_merma', title='Merma Diaria')
            st.plotly_chart(fig, use_container_width=True)
    
    with tab3:
        st.subheader("Historial de Merma")
        col1, col2, col3 = st.columns(3)
        with col1:
            fecha_hist_inicio = st.date_input("Fecha inicio:", datetime.now().date() - timedelta(days=30), key="merma_hist_inicio")
        with col2:
            fecha_hist_fin = st.date_input("Fecha fin:", datetime.now().date(), key="merma_hist_fin")
        with col3:
            invernaderos_filtro = [("", "Todos")] + [(id_inv, nombre) for id_inv, nombre, _ in get_invernaderos()]
            invernadero_filtro = st.selectbox("Filtrar por invernadero:", invernaderos_filtro, format_func=lambda x: x[1] if isinstance(x, tuple) else x, key="merma_invernadero_filtro")
        
        invernadero_id_filtro = invernadero_filtro[0] if invernadero_filtro and invernadero_filtro[0] else None
        merma = get_merma(fecha_hist_inicio, fecha_hist_fin, invernadero_id_filtro)
        
        if not merma.empty:
            st.dataframe(merma, use_container_width=True)
            output = export_to_excel(merma, "Merma")
            st.download_button("📥 Exportar a Excel", data=output, file_name=f"merma_{datetime.now().date()}.xlsx")

def mostrar_gestion_invernaderos():
    st.header("🏭 Gestión de Invernaderos")
    
    with st.expander("➕ Agregar Nuevo Invernadero"):
        with st.form("form_invernadero"):
            nombre_invernadero = st.text_input("Nombre del Invernadero *", key="nombre_invernadero")
            ubicacion_invernadero = st.text_input("Ubicación *", key="ubicacion_invernadero")
            
            if st.form_submit_button("Guardar Invernadero"):
                if nombre_invernadero and ubicacion_invernadero:
                    success, msg = add_invernadero(nombre_invernadero, ubicacion_invernadero)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
                else:
                    st.error("Complete todos los campos")
    
    st.markdown("---")
    st.subheader("Lista de Invernaderos")
    
    invernaderos = get_invernaderos()
    if invernaderos:
        for id_inv, nombre, ubicacion in invernaderos:
            with st.container():
                cols = st.columns([3, 1, 1])
                
                with cols[0]:
                    st.write(f"**{nombre}**")
                    st.write(f"📍 {ubicacion}")
                
                with cols[1]:
                    if st.button("✏️ Editar", key=f"edit_inv_{id_inv}"):
                        st.session_state[f'editing_inv_{id_inv}'] = True
                
                with cols[2]:
                    if st.button("🗑️ Eliminar", key=f"del_inv_{id_inv}"):
                        success, msg = delete_invernadero(id_inv)
                        if success:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
                
                if st.session_state.get(f'editing_inv_{id_inv}', False):
                    with st.form(key=f"form_edit_inv_{id_inv}"):
                        nuevo_nombre = st.text_input("Nombre", value=nombre, key=f"edit_nombre_{id_inv}")
                        nueva_ubicacion = st.text_input("Ubicación", value=ubicacion, key=f"edit_ubicacion_{id_inv}")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.form_submit_button("💾 Guardar"):
                                success, msg = update_invernadero(id_inv, nuevo_nombre, nueva_ubicacion)
                                if success:
                                    st.success(msg)
                                    del st.session_state[f'editing_inv_{id_inv}']
                                    st.rerun()
                                else:
                                    st.error(msg)
                        with col2:
                            if st.form_submit_button("❌ Cancelar"):
                                del st.session_state[f'editing_inv_{id_inv}']
                                st.rerun()
                
                st.markdown("---")
    else:
        st.info("No hay invernaderos registrados")

def mostrar_generar_qr():
    st.header("🔧 Generar Códigos QR")
    
    url_base = st.text_input("URL Base del Sistema", value=st.session_state.get('url_base', "https://tu-app.streamlit.app"), key="url_base_qr")
    st.session_state.url_base = url_base
    
    trabajadores = get_all_workers()
    
    if not trabajadores.empty:
        st.subheader("📱 Generar QR por Trabajador")
        opcion = st.radio("Seleccionar:", ["Todos", "Seleccionar específicos"], key="opcion_qr")
        
        if opcion == "Todos":
            trabajadores_seleccionados = trabajadores.to_dict('records')
        else:
            nombres = [f"{row['id']} - {row['nombre']} {row['apellido_paterno']}" for _, row in trabajadores.iterrows()]
            seleccionados = st.multiselect("Selecciona trabajadores", nombres, key="trabajadores_seleccionados")
            trabajadores_seleccionados = [row for _, row in trabajadores.iterrows() if f"{row['id']} - {row['nombre']} {row['apellido_paterno']}" in seleccionados]
        
        if st.button("🔄 Generar QR", use_container_width=True, key="btn_generar_qr"):
            for trabajador in trabajadores_seleccionados:
                id_trabajador = trabajador['id']
                nombre_completo = f"{trabajador['nombre']} {trabajador['apellido_paterno']}"
                qr_bytes = generar_qr_trabajador_simple(str(id_trabajador), nombre_completo, url_base)
                
                col1, col2 = st.columns([1, 2])
                with col1: st.image(qr_bytes, width=150)
                with col2:
                    st.write(f"**{nombre_completo}**")
                    st.write(f"ID: {id_trabajador}")
                    st.download_button("📥 Descargar QR", data=qr_bytes, file_name=f"QR_{id_trabajador}_{nombre_completo.replace(' ', '_')}.png", mime="image/png", key=f"download_qr_{id_trabajador}")
        
        if st.button("📦 Descargar Todos en ZIP", use_container_width=True, key="btn_zip_qr"):
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for _, trabajador in trabajadores.iterrows():
                    nombre_completo = f"{trabajador['nombre']} {trabajador['apellido_paterno']}"
                    qr_bytes = generar_qr_trabajador_simple(str(trabajador['id']), nombre_completo, url_base)
                    zip_file.writestr(f"QR_{trabajador['id']}_{nombre_completo.replace(' ', '_')}.png", qr_bytes.getvalue())
            zip_buffer.seek(0)
            st.download_button("📥 Descargar ZIP", data=zip_buffer, file_name=f"todos_qr_{datetime.now().strftime('%Y%m%d')}.zip", mime="application/zip")
    else:
        st.warning("Primero agrega trabajadores en '👥 Gestión Personal'")

def mostrar_reportes_qr():
    st.header("📊 Reportes de Escaneos QR")
    
    col1, col2 = st.columns([1, 3])
    with col1:
        fecha_filtro = st.date_input("Filtrar por fecha", value=None, key="fecha_filtro_qr")
    
    try:
        query = supabase.table('registros_escaneo').select('*')
        
        if fecha_filtro:
            query = query.eq('fecha_escaneo', fecha_filtro.strftime("%d/%m/%Y"))
        
        result = query.order('fecha_registro', desc=True).execute()
        
        registros = pd.DataFrame(result.data) if result.data else pd.DataFrame()
        
        if not registros.empty:
            st.dataframe(registros, use_container_width=True)
            
            col1, col2, col3, col4 = st.columns(4)
            with col1: st.metric("Total Registros", len(registros))
            with col2: st.metric("Trabajadores Únicos", registros['id_trabajador'].nunique() if 'id_trabajador' in registros.columns else 0)
            with col3: st.metric("Fecha", fecha_filtro.strftime("%d/%m/%Y") if fecha_filtro else "Todos")
            with col4: pass
            
            if 'fecha_escaneo' in registros.columns:
                registros_por_dia = registros.groupby('fecha_escaneo').size().reset_index(name='Cantidad')
                fig = px.bar(registros_por_dia, x='fecha_escaneo', y='Cantidad', title='Escaneos por Día')
                st.plotly_chart(fig, use_container_width=True)
            
            output = io.BytesIO()
            registros.to_excel(output, index=False)
            output.seek(0)
            st.download_button("📥 Exportar a Excel", data=output, file_name=f"registros_qr_{datetime.now().strftime('%Y%m%d')}.xlsx")
        else:
            st.info("No hay registros de escaneos")
    except Exception as e:
        st.error(f"Error al obtener registros: {str(e)}")
        st.info("No hay registros de escaneos")

def mostrar_reportes():
    st.header("📊 Reportes")
    
    tab1, tab2, tab3 = st.tabs(["📥 Ingresos", "📤 Bajas", "📋 Nómina Activa"])
    
    with tab1:
        st.subheader("Ingresos de la Semana")
        if st.button("Generar reporte", key="btn_ingresos", use_container_width=True):
            df, inicio, fin = get_report_ingresos_semana()
            if df.empty:
                st.warning(f"No hay ingresos entre {inicio.date()} y {fin.date()}")
            else:
                st.success(f"Encontrados: {len(df)}")
                st.dataframe(df, use_container_width=True)
                output = export_to_excel(df, "Ingresos")
                st.download_button("📥 Descargar Excel", data=output, file_name=f"ingresos_{inicio.date()}.xlsx")
    
    with tab2:
        st.subheader("Bajas de la Semana")
        if st.button("Generar reporte", key="btn_bajas", use_container_width=True):
            df, inicio, fin = get_report_bajas_semana()
            if df.empty:
                st.warning(f"No hay bajas entre {inicio.date()} y {fin.date()}")
            else:
                st.success(f"Encontradas: {len(df)}")
                st.dataframe(df, use_container_width=True)
                output = export_to_excel(df, "Bajas")
                st.download_button("📥 Descargar Excel", data=output, file_name=f"bajas_{inicio.date()}.xlsx")
    
    with tab3:
        st.subheader("Nómina Activa")
        col1, col2 = st.columns(2)
        with col1:
            deptos_list = ["Todos"] + get_departamentos_nombres()
            depto = st.selectbox("Departamento", deptos_list, key="depto_nomina")
        with col2:
            subs_list = ["Todos"] + get_subdepartamentos_nombres()
            sub = st.selectbox("Subdepartamento", subs_list, key="sub_nomina")
        
        if st.button("Generar reporte", key="btn_nomina", use_container_width=True):
            df, resumen = get_report_nomina_activa(depto, sub)
            if df.empty:
                st.warning("No hay trabajadores activos")
            else:
                st.success(f"Total: {len(df)}")
                st.subheader("Resumen por Departamento")
                st.dataframe(resumen, use_container_width=True)
                st.subheader("Detalle de Trabajadores")
                st.dataframe(df, use_container_width=True)
                
                output = BytesIO()
                with pd.ExcelWriter(output, engine="openpyxl") as writer:
                    df.to_excel(writer, index=False, sheet_name="Nómina Activa")
                    resumen.to_excel(writer, index=False, sheet_name="Resumen")
                output.seek(0)
                st.download_button("📥 Descargar Excel", data=output, file_name=f"nomina_activa_{datetime.now().date()}.xlsx")

def mostrar_catalogos():
    st.header("📋 Gestión de Catálogos")
    
    tab1, tab2, tab3 = st.tabs(["🏢 Departamentos", "📂 Subdepartamentos", "💼 Puestos"])
    
    for tab, tabla, get_func in [(tab1, "departamentos", get_departamentos), 
                                   (tab2, "subdepartamentos", get_subdepartamentos), 
                                   (tab3, "puestos", get_puestos)]:
        with tab:
            with st.form(f"new_{tabla}"):
                nuevo = st.text_input(f"Nuevo {tabla[:-1]}", key=f"nuevo_{tabla}")
                if st.form_submit_button("➕ Agregar"):
                    if nuevo:
                        success, msg = add_catalog_item(tabla, nuevo)
                        if success:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
            
            st.markdown("---")
            items = get_func()
            for id_item, nombre in items:
                cols = st.columns([4, 1, 1])
                with cols[0]: st.write(f"**{nombre}**")
                with cols[1]:
                    if st.button("✏️ Editar", key=f"edit_{tabla}_{id_item}"):
                        st.session_state[f'editing_{tabla}_{id_item}'] = True
                with cols[2]:
                    if st.button("🗑️ Eliminar", key=f"del_{tabla}_{id_item}"):
                        st.session_state[f'deleting_{tabla}_{id_item}'] = True
                
                if st.session_state.get(f'editing_{tabla}_{id_item}', False):
                    with st.form(key=f"form_edit_{tabla}_{id_item}"):
                        nuevo_nombre = st.text_input("Editar nombre", value=nombre, key=f"edit_nombre_{tabla}_{id_item}")
                        if st.form_submit_button("💾 Guardar"):
                            success, msg = update_catalog_item(tabla, id_item, nuevo_nombre)
                            if success:
                                st.success(msg)
                                del st.session_state[f'editing_{tabla}_{id_item}']
                                st.rerun()
                
                if st.session_state.get(f'deleting_{tabla}_{id_item}', False):
                    st.warning(f"¿Eliminar '{nombre}'?")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✅ Sí", key=f"conf_del_{tabla}_{id_item}"):
                            success, msg = delete_catalog_item(tabla, id_item)
                            if success:
                                st.success(msg)
                                del st.session_state[f'deleting_{tabla}_{id_item}']
                                st.rerun()
                    with col2:
                        if st.button("❌ No", key=f"cancel_del_{tabla}_{id_item}"):
                            del st.session_state[f'deleting_{tabla}_{id_item}']
                st.markdown("---")

def mostrar_proyecciones():
    st.header("📈 Proyecciones de Cajas por Semana")
    
    st.markdown("""
    <div style="background-color: #e3f2fd; padding: 15px; border-radius: 10px; margin-bottom: 20px;">
        <strong>📌 Información:</strong><br>
        • Registre las proyecciones de cajas por semana (valor global, sin especificar invernadero)<br>
        • El sistema sumará automáticamente la producción real de todos los invernaderos para comparar<br>
        • Se calculará el déficit/superávit semanal y total
    </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["📝 Registrar Proyección", "📊 Comparativa Real vs Proyectado", "📋 Historial"])
    
    with tab1:
        st.subheader("Registrar Nueva Proyección Semanal")
        
        semana_actual = datetime.now().isocalendar()[1]
        
        col_semana_actual = st.columns([1, 2, 1])
        with col_semana_actual[1]:
            st.markdown(f"""
            <div class="week-card" style="margin-bottom: 20px;">
                <div style="font-size: 12px; color: rgba(255,255,255,0.8);">📆 SEMANA ACTUAL</div>
                <div style="font-size: 24px; font-weight: bold; color: white;">{semana_actual}</div>
            </div>
            """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            semana = st.number_input(
                "Semana *",
                min_value=1,
                max_value=52,
                value=semana_actual,
                step=1,
                key="semana_proyeccion"
            )
        
        with col2:
            cajas_proyectadas = st.number_input(
                "Cajas Proyectadas *",
                min_value=0.0,
                step=50.0,
                value=0.0,
                key="cajas_proyectadas"
            )
        
        registrado_por = st.text_input("Registrado por *", placeholder="Nombre de quien registra la proyección", key="registrado_por_proyeccion")
        observaciones = st.text_area("Observaciones", placeholder="Notas adicionales sobre la proyección...", key="obs_proyeccion")
        
        proyeccion_existente = get_proyecciones(semana=semana)
        if not proyeccion_existente.empty:
            st.info(f"⚠️ Ya existe una proyección para semana {semana}: {proyeccion_existente.iloc[0]['cajas_proyectadas']:.0f} cajas. Al guardar se actualizará.")
        
        if st.button("✅ Registrar Proyección", type="primary", use_container_width=True, key="btn_registrar_proyeccion"):
            if not registrado_por:
                st.error("❌ Ingrese quién registra la proyección")
            elif cajas_proyectadas <= 0:
                st.error("❌ Ingrese una cantidad válida de cajas proyectadas")
            else:
                success, msg = registrar_proyeccion(semana, cajas_proyectadas, registrado_por, observaciones)
                if success:
                    st.success(msg)
                    st.balloons()
                else:
                    st.error(msg)
    
    with tab2:
        st.subheader("Comparativa: Producción Real vs Proyectada")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            semana_inicio = st.number_input(
                "Semana inicio",
                min_value=1,
                max_value=52,
                value=1,
                key="comp_semana_inicio"
            )
        
        with col2:
            semana_fin = st.number_input(
                "Semana fin",
                min_value=1,
                max_value=52,
                value=datetime.now().isocalendar()[1],
                key="comp_semana_fin"
            )
        
        with col3:
            tipo_opciones = ["Todos", "Nacional", "Exportación"]
            tipo_seleccionado = st.selectbox("Tipo de Cosecha", tipo_opciones, key="comp_tipo_cosecha")
            
            presentacion_opciones = ["Todos", "6 oz", "12 oz"]
            presentacion_seleccionado = st.selectbox("Presentación", presentacion_opciones, key="comp_presentacion")
        
        if st.button("📊 Actualizar Comparativa", key="btn_actualizar_comparativa", use_container_width=True):
            df_comparativa = get_comparativa_proyeccion_real_con_filtros(
                semana_inicio, semana_fin, 
                tipo_seleccionado if tipo_seleccionado != "Todos" else None,
                presentacion_seleccionado if presentacion_seleccionado != "Todos" else None
            )
            
            if not df_comparativa.empty:
                st.success(f"Datos encontrados para {len(df_comparativa)} semanas")
                
                total_proyectado = df_comparativa['cajas_proyectadas'].sum()
                total_real = df_comparativa['cajas_reales'].sum()
                diferencia_total = total_real - total_proyectado
                porcentaje_total = (diferencia_total / total_proyectado * 100) if total_proyectado > 0 else 0
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("📊 Total Proyectado", f"{total_proyectado:,.0f} cajas")
                with col2:
                    st.metric("✅ Total Real", f"{total_real:,.0f} cajas")
                with col3:
                    st.metric("📈 Diferencia", f"{diferencia_total:+,.0f} cajas")
                with col4:
                    st.metric("📉 Porcentaje", f"{porcentaje_total:+.1f}%")
                
                st.subheader("Detalle por Semana")
                
                df_display = df_comparativa.copy()
                df_display['cajas_proyectadas'] = df_display['cajas_proyectadas'].map(lambda x: f"{x:.0f}")
                df_display['cajas_reales'] = df_display['cajas_reales'].map(lambda x: f"{x:.0f}")
                df_display['diferencia'] = df_display['diferencia'].map(lambda x: f"{x:+.0f}")
                df_display['porcentaje_desviacion'] = df_display['porcentaje_desviacion'].map(lambda x: f"{x:+.1f}%")
                
                st.dataframe(
                    df_display[['semana', 'cajas_proyectadas', 'cajas_reales', 'diferencia', 'porcentaje_desviacion', 'estado']],
                    use_container_width=True,
                    column_config={
                        "semana": "Semana",
                        "cajas_proyectadas": "Proyectadas",
                        "cajas_reales": "Reales",
                        "diferencia": "Diferencia",
                        "porcentaje_desviacion": "% Desviación",
                        "estado": "Estado"
                    }
                )
                
                st.subheader("📊 Análisis Visual")
                
                fig1 = go.Figure()
                
                fig1.add_trace(go.Bar(
                    x=df_comparativa['semana'],
                    y=df_comparativa['cajas_proyectadas'],
                    name='Proyectado',
                    marker_color='#3498db'
                ))
                fig1.add_trace(go.Bar(
                    x=df_comparativa['semana'],
                    y=df_comparativa['cajas_reales'],
                    name='Real',
                    marker_color='#2ecc71'
                ))
                
                fig1.update_layout(
                    title='Comparativa Semanal: Proyectado vs Real',
                    xaxis_title='Semana',
                    yaxis_title='Cajas',
                    barmode='group',
                    plot_bgcolor='white',
                    height=500
                )
                st.plotly_chart(fig1, use_container_width=True)
                
                fig2 = go.Figure()
                fig2.add_trace(go.Scatter(
                    x=df_comparativa['semana'],
                    y=df_comparativa['porcentaje_desviacion'],
                    mode='lines+markers',
                    name='% Desviación',
                    line=dict(color='#e74c3c', width=3),
                    marker=dict(size=8)
                ))
                
                fig2.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
                
                fig2.update_layout(
                    title='Evolución del Porcentaje de Desviación por Semana',
                    xaxis_title='Semana',
                    yaxis_title='% Desviación',
                    plot_bgcolor='white',
                    height=400
                )
                st.plotly_chart(fig2, use_container_width=True)
                
                output = export_to_excel(df_comparativa, "Comparativa_Real_Proyectado")
                st.download_button(
                    "📥 Exportar Comparativa a Excel",
                    data=output,
                    file_name=f"comparativa_proyecciones_{datetime.now().date()}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
            else:
                st.warning("No hay datos de proyecciones o producción real para el período seleccionado")
    
    with tab3:
        st.subheader("Historial de Proyecciones Registradas")
        
        col1, col2 = st.columns(2)
        
        with col1:
            semana_hist = st.number_input(
                "Filtrar por semana (opcional)",
                min_value=1,
                max_value=52,
                value=1,
                step=1,
                key="hist_semana",
                help="Seleccione una semana para filtrar"
            )
        
        semana_hist_param = semana_hist if semana_hist > 0 else None
        
        df_proyecciones = get_proyecciones(semana=semana_hist_param)
        
        if not df_proyecciones.empty:
            df_display = df_proyecciones.copy()
            df_display['fecha_registro'] = pd.to_datetime(df_display['fecha_registro']).dt.strftime('%d/%m/%Y %H:%M')
            
            st.dataframe(
                df_display[['semana', 'cajas_proyectadas', 'fecha_registro', 'registrado_por', 'observaciones']],
                use_container_width=True,
                column_config={
                    "semana": "Semana",
                    "cajas_proyectadas": "Cajas Proyectadas",
                    "fecha_registro": "Fecha Registro",
                    "registrado_por": "Registrado por",
                    "observaciones": "Observaciones"
                }
            )
            
            output = export_to_excel(df_proyecciones, "Proyecciones")
            st.download_button(
                "📥 Exportar Proyecciones a Excel",
                data=output,
                file_name=f"proyecciones_{datetime.now().date()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
            st.subheader("📊 Resumen Estadístico")
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Proyectado", f"{df_proyecciones['cajas_proyectadas'].sum():,.0f} cajas")
            with col2:
                st.metric("Promedio por Semana", f"{df_proyecciones['cajas_proyectadas'].mean():,.0f} cajas")
        else:
            st.info("No hay proyecciones registradas para los filtros seleccionados")

def mostrar_dashboard_general():
    """Dashboard profesional con diseño moderno y KPIs interactivos"""
    
    with st.sidebar:
        st.markdown("""
        <div style="text-align: center; padding: 20px; background: linear-gradient(135deg, #1e3c2c 0%, #2a6b3c 100%); border-radius: 15px; color: white; margin-bottom: 20px;">
            <h2 style="margin: 0;">🌱 Dashboard</h2>
            <p style="margin: 5px 0 0 0;">Filtros interactivos</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("### 📅 Rango de Fechas")
        fecha_default_inicio = datetime.now().date() - timedelta(days=90)
        fecha_default_fin = datetime.now().date()
        
        fecha_inicio = st.date_input("Fecha inicio", fecha_default_inicio, key="dash_fecha_inicio")
        fecha_fin = st.date_input("Fecha fin", fecha_default_fin, key="dash_fecha_fin")
        
        st.markdown("### 🏭 Invernadero")
        invernaderos = get_invernaderos()
        invernaderos_opciones = ["Todos"] + [nombre for _, nombre, _ in invernaderos]
        invernadero_seleccionado = st.selectbox("Seleccionar invernadero", invernaderos_opciones, key="dash_invernadero")
        
        st.markdown("### 🌾 Tipo de Cultivo")
        tipo_opciones = ["Todos", "Nacional", "Exportación"]
        tipo_seleccionado = st.selectbox("Seleccionar tipo", tipo_opciones, key="dash_tipo")
        
        st.markdown("### 📦 Presentación")
        presentacion_opciones = ["Todos", "6 oz", "12 oz"]
        presentacion_seleccionado = st.selectbox("Seleccionar presentación", presentacion_opciones, key="dash_presentacion")
        
        st.markdown("### 📆 Semana")
        semana_actual = datetime.now().isocalendar()[1]
        semana_seleccionada = st.number_input("Número de semana", min_value=1, max_value=52, value=semana_actual, key="dash_semana")
        
        st.markdown("---")
        st.caption("📊 Datos actualizados en tiempo real")
    
    try:
        # Obtener cosechas con filtros
        query_cosechas = supabase.table('cosechas').select("""
            *,
            invernaderos:invernadero_id (nombre),
            trabajadores:trabajador_id (nombre, apellido_paterno)
        """)
        
        if fecha_inicio:
            query_cosechas = query_cosechas.gte('fecha', fecha_inicio.isoformat())
        if fecha_fin:
            query_cosechas = query_cosechas.lte('fecha', fecha_fin.isoformat())
        
        cosechas_result = query_cosechas.order('fecha', desc=True).execute()
        
        df_cosechas = pd.DataFrame(cosechas_result.data) if cosechas_result.data else pd.DataFrame()
        
        if not df_cosechas.empty:
            if invernadero_seleccionado and invernadero_seleccionado != "Todos":
                df_cosechas = df_cosechas[df_cosechas['invernaderos'].apply(lambda x: x['nombre'] if x else '') == invernadero_seleccionado]
            if tipo_seleccionado and tipo_seleccionado != "Todos":
                df_cosechas = df_cosechas[df_cosechas['tipo_cosecha'] == tipo_seleccionado]
            if presentacion_seleccionado and presentacion_seleccionado != "Todos":
                df_cosechas = df_cosechas[df_cosechas['presentacion'] == presentacion_seleccionado]
            if semana_seleccionada:
                df_cosechas = df_cosechas[df_cosechas['semana'] == semana_seleccionada]
        
        # Obtener trabajadores
        trabajadores_result = supabase.table('trabajadores').select('*').execute()
        df_trabajadores = pd.DataFrame(trabajadores_result.data) if trabajadores_result.data else pd.DataFrame()
        
        # Obtener envíos
        query_envios = supabase.table('envios_enfriado').select("""
            *,
            invernaderos:invernadero_id (nombre)
        """)
        
        if fecha_inicio:
            query_envios = query_envios.gte('fecha', fecha_inicio.isoformat())
        if fecha_fin:
            query_envios = query_envios.lte('fecha', fecha_fin.isoformat())
        
        envios_result = query_envios.execute()
        df_envios = pd.DataFrame(envios_result.data) if envios_result.data else pd.DataFrame()
        
        if not df_envios.empty and invernadero_seleccionado and invernadero_seleccionado != "Todos":
            df_envios = df_envios[df_envios['invernaderos'].apply(lambda x: x['nombre'] if x else '') == invernadero_seleccionado]
        if semana_seleccionada and not df_envios.empty:
            df_envios = df_envios[df_envios['semana'] == semana_seleccionada]
        
        # Obtener incidencias
        query_incidencias = supabase.table('incidencias').select("""
            *,
            trabajadores:trabajador_id (nombre, apellido_paterno)
        """)
        
        if fecha_inicio:
            query_incidencias = query_incidencias.gte('fecha', fecha_inicio.isoformat())
        if fecha_fin:
            query_incidencias = query_incidencias.lte('fecha', fecha_fin.isoformat())
        
        incidencias_result = query_incidencias.execute()
        df_incidencias = pd.DataFrame(incidencias_result.data) if incidencias_result.data else pd.DataFrame()
        
        # Calcular métricas
        activos = len(df_trabajadores[df_trabajadores['estatus'] == 'activo']) if not df_trabajadores.empty else 0
        bajas = len(df_trabajadores[df_trabajadores['estatus'] == 'baja']) if not df_trabajadores.empty else 0
        total_personal = activos + bajas
        rotacion = (bajas / max(total_personal, 1)) * 100
        
        total_cajas = df_cosechas['numero_cajas'].sum() if not df_cosechas.empty else 0
        total_clams = df_cosechas['cantidad_clams'].sum() if not df_cosechas.empty else 0
        trabajadores_unicos = df_cosechas['trabajador_id'].nunique() if not df_cosechas.empty else 0
        promedio_cajas_trabajador = total_cajas / max(trabajadores_unicos, 1)
        
        total_enviadas = df_envios['cantidad_cajas'].sum() if not df_envios.empty else 0
        
        porcentaje_merma = obtener_porcentaje_merma_filtrado(df_cosechas, df_envios)
        resumen_proyecciones = get_resumen_proyecciones_total_con_filtros_dashboard(df_cosechas)
        
        total_faltas = len(df_incidencias[df_incidencias['tipo_incidencia'].str.contains('Falta', na=False)]) if not df_incidencias.empty else 0
        total_permisos = len(df_incidencias[df_incidencias['tipo_incidencia'].str.contains('Permiso', na=False)]) if not df_incidencias.empty else 0
        total_incidencias = len(df_incidencias) if not df_incidencias.empty else 0
        
    except Exception as e:
        st.error(f"Error al cargar datos: {str(e)}")
        df_cosechas = pd.DataFrame()
        df_trabajadores = pd.DataFrame()
        df_envios = pd.DataFrame()
        df_incidencias = pd.DataFrame()
        activos = bajas = total_personal = rotacion = total_cajas = total_clams = promedio_cajas_trabajador = total_enviadas = 0
        porcentaje_merma = 0
        resumen_proyecciones = {'total_proyectado': 0, 'total_real': 0, 'diferencia': 0, 'porcentaje_desviacion': 0}
        total_faltas = total_permisos = total_incidencias = 0
    
    st.markdown("""
    <style>
        .kpi-card {
            background: linear-gradient(135deg, #1e3c2c 0%, #2a6b3c 100%);
            border-radius: 15px;
            padding: 15px;
            color: white;
            text-align: center;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            margin-bottom: 15px;
        }
        .kpi-value {
            font-size: 28px;
            font-weight: bold;
        }
        .kpi-label {
            font-size: 12px;
            opacity: 0.9;
            margin-top: 5px;
        }
        .section-title {
            font-size: 24px;
            font-weight: bold;
            color: #1e3c2c;
            margin: 20px 0 15px 0;
            border-left: 4px solid #2a6b3c;
            padding-left: 15px;
        }
        .progress-card {
            background: linear-gradient(135deg, #2a6b3c 0%, #3d8f4a 100%);
            border-radius: 15px;
            padding: 20px;
            color: white;
            text-align: center;
        }
        .progress-value {
            font-size: 48px;
            font-weight: bold;
        }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="section-title">📊 KPIs Estratégicos</div>', unsafe_allow_html=True)
    
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        st.markdown(f"""
        <div class="kpi-card">
            <div>👥</div>
            <div class="kpi-value">{activos}</div>
            <div class="kpi-label">Personal Activo</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="kpi-card">
            <div>📉</div>
            <div class="kpi-value">{bajas}</div>
            <div class="kpi-label">Bajas</div>
            <div class="kpi-label">Rotación: {rotacion:.1f}%</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="kpi-card">
            <div>📦</div>
            <div class="kpi-value">{total_cajas:,.0f}</div>
            <div class="kpi-label">Cajas Cosechadas</div>
            <div class="kpi-label">🥫 {total_clams:,.0f} clams</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class="kpi-card">
            <div>❄️</div>
            <div class="kpi-value">{total_enviadas:,.0f}</div>
            <div class="kpi-label">Enviadas a Cámara Fría</div>
            <div class="kpi-label">{ (total_enviadas/max(total_cajas,1)*100):.1f}% del total</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col5:
        if porcentaje_merma > 0:
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #ff6b6b 0%, #c44545 100%);
                        border-radius: 15px; padding: 20px; color: white; text-align: center; margin-bottom: 15px;">
                <div style="font-size: 14px; opacity: 0.9;">📉 PORCENTAJE DE MERMA</div>
                <div style="font-size: 48px; font-weight: bold;">{porcentaje_merma:.2f}%</div>
                <div style="font-size: 12px; margin-top: 5px;">(Kilos enviados / Peso de caja) / Cosecha total</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #95a5a6 0%, #7f8c8d 100%);
                        border-radius: 15px; padding: 20px; color: white; text-align: center; margin-bottom: 15px;">
                <div style="font-size: 14px; opacity: 0.9;">📉 PORCENTAJE DE MERMA</div>
                <div style="font-size: 48px; font-weight: bold;">0.00%</div>
                <div style="font-size: 12px; margin-top: 5px;">Sin datos en el rango seleccionado</div>
            </div>
            """, unsafe_allow_html=True)
    
    with col6:
        porcentaje_deficit = resumen_proyecciones['porcentaje_desviacion']
        
        if porcentaje_deficit >= 0:
            color_gradient = "linear-gradient(135deg, #2ecc71 0%, #27ae60 100%)"
            icono = "📈"
            texto_estado = "SUPERÁVIT"
        else:
            color_gradient = "linear-gradient(135deg, #e74c3c 0%, #c0392b 100%)"
            icono = "📉"
            texto_estado = "DÉFICIT"
        
        st.markdown(f"""
        <div style="background: {color_gradient};
                    border-radius: 15px; padding: 20px; color: white; text-align: center; margin-bottom: 15px;">
            <div style="font-size: 14px; opacity: 0.9;">{icono} PROYECCIÓN VS REAL</div>
            <div style="font-size: 48px; font-weight: bold;">{abs(porcentaje_deficit):.2f}%</div>
            <div style="font-size: 12px; margin-top: 5px;">{texto_estado} - Proyectado: {resumen_proyecciones['total_proyectado']:,.0f} cajas | Real: {resumen_proyecciones['total_real']:,.0f} cajas</div>
        </div>
        """, unsafe_allow_html=True)
    
    col7, col8, col9, col10 = st.columns(4)
    
    with col7:
        st.markdown(f"""
        <div class="kpi-card">
            <div>👨‍🌾</div>
            <div class="kpi-value">{promedio_cajas_trabajador:.1f}</div>
            <div class="kpi-label">Promedio x Trabajador</div>
            <div class="kpi-label">cajas por persona</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col8:
        st.markdown(f"""
        <div class="kpi-card">
            <div>✅</div>
            <div class="kpi-value">0.0%</div>
            <div class="kpi-label">Tasa de Asistencia</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col9:
        st.markdown(f"""
        <div class="kpi-card">
            <div>⚠️</div>
            <div class="kpi-value">{total_faltas + total_permisos}</div>
            <div class="kpi-label">Faltas y Permisos</div>
            <div class="kpi-label">🚫 Faltas: {total_faltas} | 📝 Permisos: {total_permisos}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col10:
        st.markdown(f"""
        <div class="kpi-card">
            <div>📋</div>
            <div class="kpi-value">{total_incidencias}</div>
            <div class="kpi-label">Total Incidencias</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('<div class="section-title">🌾 Avance de Cosecha del Día</div>', unsafe_allow_html=True)
    
    df_avance = get_avance_hoy_por_invernadero()
    
    if not df_avance.empty:
        df_avance_filtrado = df_avance
        if invernadero_seleccionado and invernadero_seleccionado != "Todos":
            df_avance_filtrado = df_avance[df_avance['invernadero_nombre'] == invernadero_seleccionado]
        
        st.dataframe(
            df_avance_filtrado[['invernadero_nombre', 'lineas_cosechadas', 'lineas_totales', 'porcentaje', 'supervisor', 'hora', 'turno']],
            use_container_width=True,
            column_config={
                "invernadero_nombre": "Invernadero",
                "lineas_cosechadas": "Líneas Cosechadas",
                "lineas_totales": "Líneas Totales",
                "porcentaje": "Porcentaje",
                "supervisor": "Supervisor",
                "hora": "Última Hora",
                "turno": "Turno"
            }
        )
        
        if not df_avance_filtrado.empty:
            promedio_avance = df_avance_filtrado['porcentaje'].mean()
            
            col1, col2 = st.columns([1, 1])
            with col1:
                st.markdown(f"""
                <div class="progress-card">
                    <div>📊 Promedio General</div>
                    <div class="progress-value">{promedio_avance:.1f}%</div>
                    <div>de avance en todos los invernaderos</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                total_lineas_cosechadas = df_avance_filtrado['lineas_cosechadas'].sum()
                total_lineas_totales = df_avance_filtrado['lineas_totales'].sum()
                porcentaje_total = (total_lineas_cosechadas / total_lineas_totales) * 100 if total_lineas_totales > 0 else 0
                
                st.markdown(f"""
                <div style="background-color: #f8f9fa; padding: 15px; border-radius: 10px; text-align: center;">
                    <div>📈 Progreso Total del Día</div>
                    <div style="font-size: 24px; font-weight: bold;">{total_lineas_cosechadas:,.0f} / {total_lineas_totales:,.0f} líneas</div>
                    <div style="font-size: 18px; font-weight: bold; color: #2a6b3c;">{porcentaje_total:.1f}%</div>
                </div>
                """, unsafe_allow_html=True)
            
            fig = px.bar(df_avance_filtrado, x='invernadero_nombre', y='porcentaje',
                        title='Porcentaje de Avance por Invernadero (Hoy)',
                        labels={'invernadero_nombre': 'Invernadero', 'porcentaje': 'Porcentaje (%)'},
                        text='porcentaje',
                        color='porcentaje',
                        color_continuous_scale='Greens')
            fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
            fig.update_layout(plot_bgcolor='white', height=400)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay datos para mostrar con los filtros seleccionados")
    else:
        st.info("No hay registros de avance para el día de hoy")
    
    st.markdown('<div class="section-title">🌾 Producción Agrícola</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        if not df_cosechas.empty:
            df_semanal = df_cosechas.groupby('semana')['numero_cajas'].sum().reset_index().sort_values('semana')
            fig = px.line(df_semanal, x='semana', y='numero_cajas', 
                         title='Cajas Cosechadas por Semana',
                         labels={'semana': 'Semana', 'numero_cajas': 'Cajas'})
            fig.update_traces(line=dict(color='#2a6b3c', width=3))
            fig.update_layout(plot_bgcolor='white', height=400)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay datos de cosechas para mostrar")
    
    with col2:
        if not df_cosechas.empty and 'invernaderos' in df_cosechas.columns:
            df_cosechas['invernadero_nombre'] = df_cosechas['invernaderos'].apply(lambda x: x['nombre'] if x else 'Desconocido')
            df_inv = df_cosechas.groupby('invernadero_nombre')['numero_cajas'].sum().reset_index().sort_values('numero_cajas', ascending=True)
            fig = px.bar(df_inv, x='numero_cajas', y='invernadero_nombre', orientation='h',
                        title='Cajas por Invernadero',
                        labels={'numero_cajas': 'Cajas', 'invernadero_nombre': 'Invernadero'},
                        color='numero_cajas', color_continuous_scale='Greens')
            fig.update_layout(plot_bgcolor='white', height=400)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay datos de invernaderos para mostrar")
    
    st.markdown('<div class="section-title">📈 Análisis de Producción</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        if not df_cosechas.empty or not df_envios.empty:
            fig = go.Figure()
            
            if not df_cosechas.empty:
                df_cosech_semanal = df_cosechas.groupby('semana')['numero_cajas'].sum().reset_index().sort_values('semana')
                fig.add_trace(go.Scatter(
                    x=df_cosech_semanal['semana'], y=df_cosech_semanal['numero_cajas'],
                    mode='lines+markers', name='Producción',
                    line=dict(color='#2a6b3c', width=3), marker=dict(size=8)
                ))
            
            if not df_envios.empty:
                df_env_semanal = df_envios.groupby('semana')['cantidad_cajas'].sum().reset_index().sort_values('semana')
                fig.add_trace(go.Scatter(
                    x=df_env_semanal['semana'], y=df_env_semanal['cantidad_cajas'],
                    mode='lines+markers', name='Envíos',
                    line=dict(color='#e67e22', width=3), marker=dict(size=8)
                ))
            
            fig.update_layout(title='Producción vs Envíos por Semana', xaxis_title='Semana', yaxis_title='Cajas', plot_bgcolor='white', height=400)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay datos de producción o envíos para mostrar")
    
    with col2:
        if not df_cosechas.empty:
            df_prod = df_cosechas.groupby(['tipo_cosecha', 'presentacion'])['numero_cajas'].sum().reset_index()
            fig = px.bar(df_prod, x='tipo_cosecha', y='numero_cajas', color='presentacion',
                        title='Producción por Tipo y Presentación',
                        labels={'numero_cajas': 'Cajas', 'tipo_cosecha': 'Tipo'},
                        barmode='group', color_discrete_sequence=['#2a6b3c', '#55b36a'])
            fig.update_layout(plot_bgcolor='white', height=400)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay datos de producción para mostrar")
    
    with st.expander("📋 Ver detalle de datos", expanded=False):
        st.markdown("### 📦 Últimas cosechas")
        if not df_cosechas.empty:
            display_df = df_cosechas[['fecha', 'semana', 'tipo_cosecha', 'presentacion', 'numero_cajas', 'cajas_enviadas']].head(10)
            st.dataframe(display_df, use_container_width=True)
        
        st.markdown("### 📤 Últimos envíos")
        if not df_envios.empty:
            st.dataframe(df_envios.head(10), use_container_width=True)
        
        st.markdown("### ⚠️ Incidencias recientes")
        if not df_incidencias.empty:
            st.dataframe(df_incidencias.head(10), use_container_width=True)

def mostrar_menu_sidebar():
    """Muestra el menú lateral con opciones según el rol del usuario"""
    
    st.sidebar.markdown("""
    <div class="sidebar-title">
        <h2>🌾 Sistema Integral</h2>
        <p>Gestión Agrícola</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Información del usuario
    if st.session_state.get('authenticated', False):
        st.sidebar.markdown(f"""
        <div class="user-info">
            👤 <strong>{st.session_state.get('user_nombre', 'Usuario')}</strong><br>
            📧 {st.session_state.get('user_email', '')}<br>
            🎭 Rol: <strong>{st.session_state.get('user_rol', 'supervisor').upper()}</strong>
        </div>
        """, unsafe_allow_html=True)
    
    # Menú para administradores (acceso completo)
    if st.session_state.get('user_rol') == 'admin':
        menu_options = {
            "🌾 Registro Cosecha": "Registrar producción",
            "👥 Gestión Personal": "Alta/baja/editar trabajadores",
            "📊 Dashboard": "Estadísticas generales",
            "📈 Proyecciones": "Comparativa real vs proyectado",
            "🕐 Control Asistencia": "Registro entrada/salida",
            "📊 Avance Cosecha": "Registrar avance por invernadero",
            "❄️ Envíos a Enfriado": "Cajas a enfriado",
            "🗑️ Gestión Merma": "Registro de merma",
            "📱 Generar QR": "Códigos QR para trabajadores",
            "📊 Registros QR": "Reportes de escaneos QR",
            "📋 Reportes": "Reportes y estadísticas",
            "📚 Catálogos": "Departamentos, puestos, etc.",
            "🏭 Gestión Invernaderos": "Administrar invernaderos"
        }
    
    # Menú para supervisores (sin gestión personal, sin generar QR)
    else:
        menu_options = {
            "🌾 Registro Cosecha": "Registrar producción",
            "📊 Dashboard": "Estadísticas generales",
            "📈 Proyecciones": "Comparativa real vs proyectado",
            "🕐 Control Asistencia": "Registro entrada/salida",
            "📊 Avance Cosecha": "Registrar avance por invernadero",
            "❄️ Envíos a Enfriado": "Cajas a enfriado",
            "🗑️ Gestión Merma": "Registro de merma",
            "📊 Registros QR": "Reportes de escaneos QR",
            "📋 Reportes": "Reportes y estadísticas",
            "🏭 Gestión Invernaderos": "Administrar invernaderos"
        }
    
    for option, desc in menu_options.items():
        if st.sidebar.button(option, use_container_width=True, help=desc, key=f"menu_{option.replace(' ', '_')}"):
            st.session_state.menu = option
            st.rerun()
    
    # Botón de cerrar sesión
    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Cerrar Sesión", use_container_width=True):
        logout_user()

# ==========================================
# FUNCIÓN PRINCIPAL
# ==========================================

def main():
    # Inicializar Supabase
    global supabase
    supabase = init_supabase()
    
    if supabase is None:
        st.error("❌ No se pudo conectar a Supabase. Verifica tu configuración.")
        st.stop()
    
    # Inicializar variables de sesión
    if 'menu' not in st.session_state:
        st.session_state.menu = "📊 Dashboard"
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    # Verificar autenticación
    if not st.session_state.authenticated:
        show_login_page()
        return
    
    # Mostrar menú y contenido
    mostrar_menu_sidebar()
    
    # Navegación según el menú seleccionado
    if st.session_state.menu == "🌾 Registro Cosecha":
        st.header("🌾 Registro de Cosecha")
        tab1, tab2 = st.tabs(["📷 Escanear QR", "📝 Registrar Manual"])
        
        with tab1:
            escanear_qr_con_camara(tipo_evento="cosecha", mostrar_invernadero=True)
        
        with tab2:
            formulario_cosecha_manual()
        
        with st.expander("📋 Ver Cosechas Registradas"):
            cosechas = get_cosechas()
            if not cosechas.empty:
                st.dataframe(cosechas, use_container_width=True)
                output = export_to_excel(cosechas, "Cosechas")
                st.download_button("📥 Exportar a Excel", data=output, file_name=f"cosechas_{datetime.now().date()}.xlsx")
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
    
    elif st.session_state.menu == "❄️ Envíos a Enfriado":
        mostrar_envios_enfriado()
    
    elif st.session_state.menu == "🗑️ Gestión Merma":
        mostrar_gestion_merma()
    
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

if __name__ == "__main__":
    main()
