import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from io import BytesIO
import re
import qrcode
from PIL import Image
import os
import json
import plotly.express as px
import plotly.graph_objects as go
import cv2
import numpy as np
from pyzbar.pyzbar import decode
import time
import io
import zipfile
from supabase import create_client, Client
import bcrypt
from functools import wraps
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

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

# ==========================================
# CONFIGURACIÓN INICIAL DE STREAMLIT
# ==========================================

st.set_page_config(
    page_title="Sistema Integral de Gestión Agrícola",
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
        max-width: 500px;
        margin: 50px auto;
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
    </style>
""", unsafe_allow_html=True)

# ==========================================
# FUNCIONES DE AUTENTICACIÓN
# ==========================================

def obtener_permisos_usuario(user_id):
    """Obtiene los permisos del usuario desde Supabase"""
    try:
        result = supabase.table('perfiles_usuario').select('permisos, rol, invernaderos_asignados').eq('id', user_id).execute()
        if result.data:
            return result.data[0].get('permisos', {}), result.data[0].get('rol'), result.data[0].get('invernaderos_asignados', [])
    except:
        pass
    return {}, 'supervisor', []

def tiene_permiso(permiso):
    """Decorador para verificar permisos"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not st.session_state.get('authenticated', False):
                show_login_page()
                return None
            permisos, rol, _ = obtener_permisos_usuario(st.session_state.get('user_id'))
            if rol == 'admin' or permisos.get(permiso, False):
                return func(*args, **kwargs)
            else:
                st.error(f"❌ No tienes permiso para acceder a esta sección")
                return None
        return wrapper
    return decorator

def get_configuracion_sistema(clave):
    """Obtiene la configuración del sistema"""
    try:
        result = supabase.table('configuracion_sistema').select('valor').eq('clave', clave).execute()
        if result.data:
            return result.data[0]['valor'] == 'true'
    except:
        pass
    return True

def login_user(email, password):
    """Autentica un usuario con Supabase Auth"""
    try:
        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        
        if response.user:
            # Obtener perfil del usuario
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
            
            return {
                'success': True,
                'user_id': response.user.id,
                'email': email,
                'rol': rol,
                'nombre': nombre,
                'permisos': permisos,
                'invernaderos_asignados': invernaderos_asignados
            }
    except Exception as e:
        error_msg = str(e)
        if "Invalid login credentials" in error_msg:
            return {'success': False, 'error': 'Email o contraseña incorrectos'}
        return {'success': False, 'error': error_msg}
    
    return {'success': False, 'error': 'Error de autenticación'}

def register_user(email, password, nombre, rol='supervisor', permisos=None, invernaderos_asignados=None):
    """Registra un nuevo usuario"""
    try:
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
            permisos_default = {
                "gestion_personal": False,
                "registro_cosecha": True,
                "registro_asistencia": True,
                "avance_cosecha": True,
                "envios_enfriado": True,
                "gestion_merma": True,
                "proyecciones": True,
                "generar_qr": False,
                "reportes": True,
                "catalogos": False,
                "gestion_invernaderos": False,
                "dashboard": True,
                "pesaje_cajas": False,
                "cajas_mesa": False,
                "cierre_dia": False,
                "gestion_usuarios": False
            }
            
            if permisos:
                permisos_default.update(permisos)
            
            supabase.table('perfiles_usuario').insert({
                'id': response.user.id,
                'email': email,
                'nombre': nombre,
                'rol': rol,
                'permisos': permisos_default,
                'invernaderos_asignados': invernaderos_asignados or []
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
    
    for key in ['user_id', 'user_email', 'user_rol', 'user_nombre', 'authenticated', 'user_permisos', 'user_invernaderos']:
        if key in st.session_state:
            del st_session[key]
    st.rerun()

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
    """Limpia la caché de Streamlit"""
    st.cache_data.clear()

def export_to_excel(df, sheet_name="Datos"):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    output.seek(0)
    return output

def get_invernaderos_usuario():
    """Obtiene los invernaderos a los que tiene acceso el usuario"""
    if st.session_state.get('user_rol') == 'admin':
        return get_all_invernaderos()
    else:
        invernaderos_asignados = st.session_state.get('user_invernaderos', [])
        if not invernaderos_asignados:
            return []
        result = supabase.table('invernaderos').select('id, nombre, ubicacion').in_('id', invernaderos_asignados).eq('activo', True).execute()
        return [(row['id'], row['nombre'], row['ubicacion']) for row in result.data] if result.data else []

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

def get_all_invernaderos():
    try:
        result = supabase.table('invernaderos').select('id, nombre, ubicacion, lineas_totales').eq('activo', True).order('nombre').execute()
        return [(row['id'], row['nombre'], row['ubicacion'], row['lineas_totales']) for row in result.data]
    except:
        return []

def get_trabajadores():
    try:
        result = supabase.table('trabajadores').select("""
            id, nombre, apellido_paterno, apellido_materno, puesto_id, puestos:puesto_id (nombre)
        """).eq('estatus', 'activo').execute()
        
        trabajadores = []
        for row in result.data:
            puesto_nombre = row['puestos']['nombre'] if row['puestos'] else ''
            trabajadores.append({
                'id': row['id'],
                'nombre_completo': f"{row['nombre']} {row['apellido_paterno']}",
                'puesto': puesto_nombre
            })
        return trabajadores
    except:
        return []

def get_recolectores():
    """Obtiene los trabajadores con puesto de Cosechador o similar"""
    try:
        result = supabase.table('trabajadores').select("""
            id, nombre, apellido_paterno
        """).eq('estatus', 'activo').execute()
        
        return [(row['id'], f"{row['nombre']} {row['apellido_paterno']}") for row in result.data]
    except:
        return []

# ==========================================
# FUNCIONES DE TRABAJADORES
# ==========================================

def get_all_workers():
    try:
        result = supabase.table('trabajadores').select("""
            id, nombre, apellido_paterno, apellido_materno, correo, telefono, 
            estatus, fecha_alta, fecha_baja, tipo_nomina,
            departamentos:departamento_id (nombre),
            subdepartamentos:subdepartamento_id (nombre),
            puestos:puesto_id (nombre)
        """).order('apellido_paterno').execute()
        
        data = []
        for row in result.data:
            data.append({
                'id': row['id'],
                'nombre': row['nombre'],
                'apellido_paterno': row['apellido_paterno'],
                'apellido_materno': row['apellido_materno'] or '',
                'correo': row['correo'] or '',
                'telefono': row['telefono'] or '',
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

def get_id_by_nombre(tabla, nombre):
    try:
        result = supabase.table(tabla).select('id').eq('nombre', nombre).execute()
        if result.data:
            return result.data[0]['id']
        return None
    except:
        return None

def search_workers(search_term, estatus_filter="todos"):
    try:
        query = supabase.table('trabajadores').select("""
            id, nombre, apellido_paterno, apellido_materno, correo, telefono, estatus, fecha_alta, fecha_baja, tipo_nomina,
            departamentos:departamento_id (nombre),
            subdepartamentos:subdepartamento_id (nombre),
            puestos:puesto_id (nombre)
        """)
        
        if search_term:
            query = query.or_(f"nombre.ilike.%{search_term}%,apellido_paterno.ilike.%{search_term}%")
        
        if estatus_filter != "todos":
            query = query.eq('estatus', estatus_filter)
        
        result = query.execute()
        
        data = []
        for row in result.data:
            data.append({
                'id': row['id'],
                'nombre': row['nombre'],
                'apellido_paterno': row['apellido_paterno'],
                'apellido_materno': row['apellido_materno'] or '',
                'correo': row['correo'] or '',
                'telefono': row['telefono'] or '',
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
        return pd.DataFrame()

def update_worker(worker_id, data):
    try:
        depto_id = get_id_by_nombre("departamentos", data['departamento'])
        sub_id = get_id_by_nombre("subdepartamentos", data['subdepartamento'])
        puesto_id = get_id_by_nombre("puestos", data['puesto'])
        
        supabase.table('trabajadores').update({
            'apellido_paterno': data['apellido_paterno'],
            'apellido_materno': data['apellido_materno'],
            'nombre': data['nombre'],
            'correo': data['correo'],
            'telefono': data['telefono'],
            'departamento_id': depto_id,
            'subdepartamento_id': sub_id,
            'tipo_nomina': data['tipo_nomina'],
            'puesto_id': puesto_id,
            'estatus': data['estatus']
        }).eq('id', worker_id).execute()
        
        invalidar_cache()
        return True, "✅ Cambios guardados correctamente"
    except Exception as e:
        return False, f"❌ Error al actualizar: {str(e)}"

def dar_baja(worker_id, fecha_baja):
    try:
        supabase.table('trabajadores').update({
            'estatus': 'baja',
            'fecha_baja': fecha_baja
        }).eq('id', worker_id).execute()
        
        invalidar_cache()
        return True, f"✅ Trabajador dado de baja correctamente"
    except Exception as e:
        return False, f"❌ Error al dar de baja: {str(e)}"

def reactivar_trabajador(worker_id):
    try:
        supabase.table('trabajadores').update({
            'estatus': 'activo',
            'fecha_baja': None
        }).eq('id', worker_id).execute()
        
        invalidar_cache()
        return True, f"✅ Trabajador reactivado correctamente"
    except Exception as e:
        return False, f"❌ Error al reactivar: {str(e)}"

def get_worker_by_id(worker_id):
    try:
        result = supabase.table('trabajadores').select('*').eq('id', worker_id).execute()
        if result.data:
            return result.data[0]
        return None
    except:
        return None

# ==========================================
# FUNCIONES DE COSECHA
# ==========================================

def guardar_cosecha(data):
    try:
        if data['presentacion'] == "12 oz":
            numero_cajas = data['cantidad_clams'] / 6
        else:
            numero_cajas = data['cantidad_clams'] / 12
        
        result = supabase.table('cosechas').insert({
            'fecha': data['fecha'].isoformat(),
            'dia': data['dia'],
            'semana': data['semana'],
            'trabajador_id': data['trabajador_id'],
            'invernadero_id': data['invernadero_id'],
            'tipo_cosecha': data['tipo_cosecha'],
            'calidad': data.get('calidad'),
            'presentacion': data['presentacion'],
            'cantidad_clams': data['cantidad_clams'],
            'numero_cajas': numero_cajas,
            'cajas_enviadas': 0,
            'merma_kilos': data.get('merma_kilos', 0),
            'observaciones': data.get('observaciones', '')
        }).execute()
        
        invalidar_cache()
        return True, f"✅ Cosecha registrada correctamente - {numero_cajas:.2f} cajas"
    except Exception as e:
        return False, f"❌ Error al guardar: {str(e)}"

def get_cosechas(fecha_inicio=None, fecha_fin=None, invernadero_id=None):
    try:
        query = supabase.table('cosechas').select("""
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
            trabajador_nombre = ""
            if row['trabajadores']:
                trabajador_nombre = f"{row['trabajadores'].get('nombre', '')} {row['trabajadores'].get('apellido_paterno', '')}"
            
            data.append({
                'id': row['id'],
                'fecha': row['fecha'],
                'semana': row['semana'],
                'trabajador': trabajador_nombre,
                'invernadero': row['invernaderos']['nombre'] if row['invernaderos'] else '',
                'tipo_cosecha': row['tipo_cosecha'],
                'calidad': row.get('calidad', ''),
                'presentacion': row['presentacion'],
                'cantidad_clams': row['cantidad_clams'],
                'numero_cajas': row['numero_cajas'],
                'merma_kilos': row.get('merma_kilos', 0),
                'observaciones': row.get('observaciones', '')
            })
        return pd.DataFrame(data)
    except Exception as e:
        return pd.DataFrame()

# ==========================================
# FUNCIONES DE ENVÍOS A ENFRIADO
# ==========================================

def registrar_envio_enfriado(invernadero_id, cantidad_cajas, supervisor_id, recolector_id, tipo_envio, presentacion, lote, observaciones):
    try:
        fecha_actual = datetime.now().date()
        hora_actual = datetime.now().time().strftime("%H:%M:%S")
        semana_actual = fecha_actual.isocalendar()[1]
        
        result = supabase.table('envios_enfriado').insert({
            'fecha': fecha_actual.isoformat(),
            'hora': hora_actual,
            'semana': semana_actual,
            'invernadero_id': invernadero_id,
            'trabajador_id': supervisor_id,
            'recolector_id': recolector_id,
            'tipo_envio': tipo_envio,
            'presentacion': presentacion,
            'cantidad_cajas': cantidad_cajas,
            'lote': lote,
            'observaciones': observaciones
        }).execute()
        
        # Actualizar cajas_enviadas en cosechas
        cosechas = supabase.table('cosechas').select('id, numero_cajas, cajas_enviadas')\
            .eq('invernadero_id', invernadero_id)\
            .eq('presentacion', presentacion)\
            .order('fecha', desc=True).execute()
        
        cajas_restantes = cantidad_cajas
        for cosecha in cosechas.data:
            if cajas_restantes <= 0:
                break
            disponibles = cosecha['numero_cajas'] - cosecha['cajas_enviadas']
            if disponibles > 0:
                a_enviar = min(disponibles, cajas_restantes)
                supabase.table('cosechas').update({'cajas_enviadas': cosecha['cajas_enviadas'] + a_enviar})\
                    .eq('id', cosecha['id']).execute()
                cajas_restantes -= a_enviar
        
        invalidar_cache()
        return True, f"✅ Envío registrado correctamente - {cantidad_cajas} cajas"
    except Exception as e:
        return False, f"❌ Error al registrar: {str(e)}"

def get_envios_enfriado(fecha_inicio=None, fecha_fin=None, invernadero_id=None):
    try:
        query = supabase.table('envios_enfriado').select("""
            *, invernaderos:invernadero_id (nombre),
            trabajadores_supervisor:trabajador_id (nombre, apellido_paterno),
            trabajadores_recolector:recolector_id (nombre, apellido_paterno)
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
            supervisor = ""
            if row['trabajadores_supervisor']:
                supervisor = f"{row['trabajadores_supervisor'].get('nombre', '')} {row['trabajadores_supervisor'].get('apellido_paterno', '')}"
            recolector = ""
            if row['trabajadores_recolector']:
                recolector = f"{row['trabajadores_recolector'].get('nombre', '')} {row['trabajadores_recolector'].get('apellido_paterno', '')}"
            
            data.append({
                'id': row['id'],
                'fecha': row['fecha'],
                'hora': row['hora'],
                'invernadero': row['invernaderos']['nombre'] if row['invernaderos'] else '',
                'supervisor': supervisor,
                'recolector': recolector,
                'tipo_envio': row['tipo_envio'],
                'presentacion': row['presentacion'],
                'cantidad_cajas': row['cantidad_cajas'],
                'lote': row.get('lote', ''),
                'observaciones': row.get('observaciones', '')
            })
        return pd.DataFrame(data)
    except Exception as e:
        return pd.DataFrame()

# ==========================================
# FUNCIONES DE PESAJE DE CAJAS
# ==========================================

def registrar_pesaje_cajas(envio_id, invernadero_id, trabajador_id, presentacion, cantidad_pesadas, cajas_recibidas, nota):
    try:
        fecha_actual = datetime.now().date()
        hora_actual = datetime.now().time().strftime("%H:%M:%S")
        semana_actual = fecha_actual.isocalendar()[1]
        
        diferencia = cantidad_pesadas - cajas_recibidas
        
        result = supabase.table('pesaje_cajas').insert({
            'fecha': fecha_actual.isoformat(),
            'hora': hora_actual,
            'semana': semana_actual,
            'envio_id': envio_id,
            'invernadero_id': invernadero_id,
            'trabajador_id': trabajador_id,
            'presentacion': presentacion,
            'cantidad_cajas_pesadas': cantidad_pesadas,
            'cajas_recibidas': cajas_recibidas,
            'diferencia': diferencia,
            'nota': nota
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
            *, invernaderos:invernadero_id (nombre),
            trabajadores:trabajador_id (nombre, apellido_paterno),
            envios:envio_id (tipo_envio, presentacion)
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
                'fecha': row['fecha'],
                'hora': row['hora'],
                'invernadero': row['invernaderos']['nombre'] if row['invernaderos'] else '',
                'pesador': f"{row['trabajadores']['nombre']} {row['trabajadores']['apellido_paterno']}" if row['trabajadores'] else '',
                'presentacion': row['presentacion'],
                'cajas_pesadas': row['cantidad_cajas_pesadas'],
                'cajas_recibidas': row['cajas_recibidas'],
                'diferencia': row['diferencia'],
                'nota': row.get('nota', '')
            })
        return pd.DataFrame(data)
    except Exception as e:
        return pd.DataFrame()

# ==========================================
# FUNCIONES DE CAJAS EN MESA
# ==========================================

def registrar_cajas_mesa(invernadero_id, trabajador_id, cantidad_cajas, presentacion, solicitando_apoyo, observaciones):
    try:
        fecha_actual = datetime.now().date()
        hora_actual = datetime.now().time().strftime("%H:%M:%S")
        
        result = supabase.table('cajas_mesa').insert({
            'fecha': fecha_actual.isoformat(),
            'hora': hora_actual,
            'invernadero_id': invernadero_id,
            'trabajador_id': trabajador_id,
            'cantidad_cajas': cantidad_cajas,
            'presentacion': presentacion,
            'solicitando_apoyo': solicitando_apoyo,
            'observaciones': observaciones
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
            *, invernaderos:invernadero_id (nombre),
            trabajadores:trabajador_id (nombre, apellido_paterno)
        """)
        
        if fecha:
            query = query.eq('fecha', fecha.isoformat())
        if solo_pendientes:
            query = query.eq('atendido', False)
        
        result = query.order('created_at', desc=True).execute()
        
        data = []
        for row in result.data:
            data.append({
                'id': row['id'],
                'fecha': row['fecha'],
                'hora': row['hora'],
                'invernadero': row['invernaderos']['nombre'] if row['invernaderos'] else '',
                'trabajador': f"{row['trabajadores']['nombre']} {row['trabajadores']['apellido_paterno']}" if row['trabajadores'] else '',
                'cantidad_cajas': row['cantidad_cajas'],
                'presentacion': row['presentacion'],
                'solicita_apoyo': row['solicitando_apoyo'],
                'atendido': row['atendido'],
                'observaciones': row.get('observaciones', '')
            })
        return pd.DataFrame(data)
    except Exception as e:
        return pd.DataFrame()

def marcar_atendido_caja_mesa(caja_id, atendido_por):
    try:
        supabase.table('cajas_mesa').update({
            'atendido': True,
            'atendido_por': atendido_por
        }).eq('id', caja_id).execute()
        
        invalidar_cache()
        return True, "✅ Solicitud marcada como atendida"
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

# ==========================================
# FUNCIONES DE ASISTENCIA
# ==========================================

def registrar_evento_asistencia(trabajador_id, invernadero_id, tipo_evento):
    try:
        fecha_actual = datetime.now().date()
        hora_actual = datetime.now().time().strftime("%H:%M:%S")
        
        # Verificar si tiene un registro activo en otro invernadero
        if tipo_evento == 'entrada_invernadero':
            registro_activo = supabase.table('asistencia').select('*')\
                .eq('trabajador_id', trabajador_id)\
                .eq('fecha', fecha_actual.isoformat())\
                .neq('estado', 'finalizado')\
                .execute()
            
            if registro_activo.data:
                reg = registro_activo.data[0]
                if reg.get('invernadero_id') != invernadero_id:
                    return False, "❌ Tienes un registro activo en otro invernadero. Primero debes registrar salida."
                return False, "❌ Ya tienes un registro activo hoy"
        
        if tipo_evento == 'entrada_invernadero':
            supabase.table('asistencia').insert({
                'trabajador_id': trabajador_id,
                'invernadero_id': invernadero_id,
                'fecha': fecha_actual.isoformat(),
                'hora_entrada': hora_actual,
                'estado': 'activo'
            }).execute()
            
            supabase.table('registros_asistencia').insert({
                'trabajador_id': trabajador_id,
                'invernadero_id': invernadero_id,
                'fecha': fecha_actual.isoformat(),
                'hora': hora_actual,
                'tipo_evento': tipo_evento
            }).execute()
            
        elif tipo_evento == 'salida_invernadero':
            registro = supabase.table('asistencia').select('*')\
                .eq('trabajador_id', trabajador_id)\
                .eq('fecha', fecha_actual.isoformat())\
                .neq('estado', 'finalizado')\
                .execute()
            
            if not registro.data:
                return False, "❌ No hay registro de entrada activo"
            
            reg = registro.data[0]
            supabase.table('asistencia').update({
                'hora_salida': hora_actual,
                'estado': 'finalizado'
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
            'salida_invernadero': "✅ Salida registrada correctamente"
        }
        return True, mensajes.get(tipo_evento, "✅ Evento registrado")
        
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

def get_estado_asistencia_actual(trabajador_id):
    try:
        fecha_actual = datetime.now().date()
        result = supabase.table('asistencia').select("""
            *, invernaderos:invernadero_id (nombre)
        """).eq('trabajador_id', trabajador_id)\
            .eq('fecha', fecha_actual.isoformat())\
            .neq('estado', 'finalizado')\
            .execute()
        
        if result.data:
            reg = result.data[0]
            return {
                'estado': reg['estado'],
                'hora_entrada': reg.get('hora_entrada'),
                'invernadero': reg['invernaderos']['nombre'] if reg.get('invernaderos') else None
            }
        return None
    except:
        return None

def get_registros_asistencia(filtros=None):
    try:
        query = supabase.table('registros_asistencia').select("""
            *, trabajadores:trabajador_id (nombre, apellido_paterno),
            invernaderos:invernadero_id (nombre)
        """)
        
        if filtros:
            if filtros.get('trabajador_id'):
                query = query.eq('trabajador_id', filtros['trabajador_id'])
            if filtros.get('fecha_inicio'):
                query = query.gte('fecha', filtros['fecha_inicio'].isoformat())
            if filtros.get('fecha_fin'):
                query = query.lte('fecha', filtros['fecha_fin'].isoformat())
        
        result = query.order('fecha', desc=True).execute()
        
        data = []
        for row in result.data:
            trabajador = ""
            if row['trabajadores']:
                trabajador = f"{row['trabajadores'].get('nombre', '')} {row['trabajadores'].get('apellido_paterno', '')}"
            
            tipo_display = {
                'entrada_invernadero': 'Entrada',
                'salida_invernadero': 'Salida'
            }.get(row['tipo_evento'], row['tipo_evento'])
            
            data.append({
                'trabajador': trabajador,
                'invernadero': row['invernaderos']['nombre'] if row['invernaderos'] else '',
                'fecha': row['fecha'],
                'hora': row['hora'],
                'tipo_evento': tipo_display
            })
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

# ==========================================
# FUNCIONES DE MERMA
# ==========================================

def registrar_merma(invernadero_id, supervisor_nombre, kilos_merma, tipo_merma, observaciones, registrado_por):
    try:
        fecha_actual = datetime.now().date()
        hora_actual = datetime.now().time().strftime("%H:%M:%S")
        semana_actual = fecha_actual.isocalendar()[1]
        
        supabase.table('merma').insert({
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
        return False, f"❌ Error: {str(e)}"

def get_merma(fecha_inicio=None, fecha_fin=None, invernadero_id=None):
    try:
        query = supabase.table('merma').select("""
            *, invernaderos:invernadero_id (nombre)
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
                'fecha': row['fecha'],
                'hora': row['hora'],
                'invernadero': row['invernaderos']['nombre'] if row['invernaderos'] else '',
                'supervisor': row['supervisor_nombre'],
                'kilos': row['kilos_merma'],
                'tipo': row['tipo_merma'],
                'observaciones': row.get('observaciones', '')
            })
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

# ==========================================
# FUNCIONES DE AVANCE DE COSECHA
# ==========================================

def get_lineas_totales_invernadero(invernadero_id):
    try:
        result = supabase.table('invernaderos').select('lineas_totales').eq('id', invernadero_id).execute()
        if result.data:
            return result.data[0]['lineas_totales']
    except:
        pass
    return 40

def get_ultimo_avance_dia(invernadero_id):
    try:
        fecha_actual = datetime.now().date()
        result = supabase.table('avance_cosecha').select('*')\
            .eq('invernadero_id', invernadero_id)\
            .eq('fecha', fecha_actual.isoformat())\
            .order('created_at', desc=True)\
            .limit(1)\
            .execute()
        
        if result.data:
            return result.data[0]
        return None
    except:
        return None

def registrar_avance_cosecha(invernadero_id, lineas_cosechadas, supervisor, observaciones, turno):
    try:
        fecha_actual = datetime.now().date()
        hora_actual = datetime.now().time().strftime("%H:%M:%S")
        semana_actual = fecha_actual.isocalendar()[1]
        lineas_totales = get_lineas_totales_invernadero(invernadero_id)
        
        if lineas_cosechadas > lineas_totales:
            return False, f"❌ Las líneas cosechadas ({lineas_cosechadas}) no pueden exceder el total ({lineas_totales})"
        
        porcentaje = (lineas_cosechadas / lineas_totales) * 100
        
        supabase.table('avance_cosecha').insert({
            'invernadero_id': invernadero_id,
            'fecha': fecha_actual.isoformat(),
            'hora': hora_actual,
            'turno': turno,
            'semana': semana_actual,
            'lineas_cosechadas': lineas_cosechadas,
            'lineas_totales': lineas_totales,
            'porcentaje': porcentaje,
            'supervisor': supervisor,
            'observaciones': observaciones
        }).execute()
        
        invalidar_cache()
        return True, f"✅ Avance registrado: {porcentaje:.1f}% completado"
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

def get_avance_hoy_por_invernadero():
    try:
        fecha_actual = datetime.now().date()
        result = supabase.table('avance_cosecha').select("""
            *, invernaderos:invernadero_id (nombre, lineas_totales)
        """).eq('fecha', fecha_actual.isoformat()).execute()
        
        # Obtener último registro por invernadero
        ultimos = {}
        for row in result.data:
            inv_id = row['invernadero_id']
            if inv_id not in ultimos or row['created_at'] > ultimos[inv_id]['created_at']:
                ultimos[inv_id] = row
        
        data = []
        for inv_id, row in ultimos.items():
            data.append({
                'invernadero': row['invernaderos']['nombre'] if row['invernaderos'] else '',
                'lineas_cosechadas': row['lineas_cosechadas'],
                'lineas_totales': row['lineas_totales'],
                'porcentaje': row['porcentaje'],
                'supervisor': row['supervisor'],
                'hora': row['hora'],
                'turno': row['turno']
            })
        
        # Agregar invernaderos sin registros
        invernaderos = get_all_invernaderos()
        inv_con_datos = set([d['invernadero'] for d in data if d['invernadero']])
        
        for inv_id, inv_nombre, _, lineas in invernaderos:
            if inv_nombre not in inv_con_datos:
                data.append({
                    'invernadero': inv_nombre,
                    'lineas_cosechadas': 0,
                    'lineas_totales': lineas,
                    'porcentaje': 0,
                    'supervisor': None,
                    'hora': None,
                    'turno': None
                })
        
        return pd.DataFrame(data)
    except Exception as e:
        return pd.DataFrame()

def get_avance_historico(fecha_inicio=None, fecha_fin=None):
    try:
        if not fecha_inicio:
            fecha_inicio = datetime.now().date() - timedelta(days=30)
        if not fecha_fin:
            fecha_fin = datetime.now().date()
        
        result = supabase.table('avance_cosecha').select("""
            *, invernaderos:invernadero_id (nombre)
        """).gte('fecha', fecha_inicio.isoformat())\
            .lte('fecha', fecha_fin.isoformat())\
            .order('fecha', desc=True)\
            .execute()
        
        data = []
        for row in result.data:
            data.append({
                'fecha': row['fecha'],
                'hora': row['hora'],
                'invernadero': row['invernaderos']['nombre'] if row['invernaderos'] else '',
                'lineas_cosechadas': row['lineas_cosechadas'],
                'lineas_totales': row['lineas_totales'],
                'porcentaje': row['porcentaje'],
                'supervisor': row['supervisor'],
                'turno': row['turno']
            })
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

# ==========================================
# FUNCIONES DE PROYECCIONES
# ==========================================

def registrar_proyeccion(semana, cajas_proyectadas, registrado_por, observaciones=""):
    try:
        supabase.table('proyecciones_cajas').upsert({
            'semana': semana,
            'cajas_proyectadas': cajas_proyectadas,
            'registrado_por': registrado_por,
            'observaciones': observaciones
        }).execute()
        
        invalidar_cache()
        return True, f"✅ Proyección registrada para semana {semana}"
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

def get_proyecciones(semana=None):
    try:
        query = supabase.table('proyecciones_cajas').select('*')
        if semana:
            query = query.eq('semana', semana)
        result = query.order('semana', desc=True).execute()
        
        data = []
        for row in result.data:
            data.append({
                'semana': row['semana'],
                'cajas_proyectadas': row['cajas_proyectadas'],
                'fecha_registro': row['fecha_registro'],
                'registrado_por': row.get('registrado_por', ''),
                'observaciones': row.get('observaciones', '')
            })
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

def get_comparativa_proyeccion_real(semana_inicio=None, semana_fin=None):
    try:
        # Obtener producción real
        cosechas = supabase.table('cosechas').select('semana, numero_cajas').execute()
        
        real_dict = {}
        for row in cosechas.data:
            semana = row['semana']
            real_dict[semana] = real_dict.get(semana, 0) + row['numero_cajas']
        
        # Obtener proyecciones
        proyecciones = get_proyecciones()
        
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
            porcentaje = (diferencia / cajas_proyectadas * 100) if cajas_proyectadas > 0 else 0
            
            data.append({
                'semana': semana,
                'proyectadas': cajas_proyectadas,
                'reales': cajas_reales,
                'diferencia': diferencia,
                'porcentaje_desviacion': porcentaje
            })
        
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

# ==========================================
# FUNCIONES DE CIERRE DE DÍA
# ==========================================

def generar_reporte_cierre_dia(fecha):
    """Genera el reporte completo del día"""
    try:
        # Cosechas del día
        cosechas = get_cosechas(fecha_inicio=fecha, fecha_fin=fecha)
        
        # Envíos del día
        envios = get_envios_enfriado(fecha_inicio=fecha, fecha_fin=fecha)
        
        # Pesajes del día
        pesajes = get_pesajes(fecha_inicio=fecha, fecha_fin=fecha)
        
        # Merma del día
        merma = get_merma(fecha_inicio=fecha, fecha_fin=fecha)
        
        # Asistencia del día
        asistencia = get_registros_asistencia({'fecha_inicio': fecha, 'fecha_fin': fecha})
        
        # Avance de cosecha
        avance = get_avance_hoy_por_invernadero()
        
        # Cajas en mesa pendientes
        cajas_mesa = get_cajas_mesa(fecha=fecha, solo_pendientes=False)
        
        reporte = {
            'fecha': fecha.isoformat(),
            'resumen': {
                'total_cajas_cosechadas': cosechas['numero_cajas'].sum() if not cosechas.empty else 0,
                'total_cajas_enviadas': envios['cantidad_cajas'].sum() if not envios.empty else 0,
                'total_merma_kilos': merma['kilos'].sum() if not merma.empty else 0,
                'total_personal': asistencia['trabajador'].nunique() if not asistencia.empty else 0,
                'promedio_avance': avance['porcentaje'].mean() if not avance.empty else 0
            },
            'detalle_cosechas': cosechas.to_dict('records') if not cosechas.empty else [],
            'detalle_envios': envios.to_dict('records') if not envios.empty else [],
            'detalle_pesajes': pesajes.to_dict('records') if not pesajes.empty else [],
            'detalle_merma': merma.to_dict('records') if not merma.empty else [],
            'detalle_cajas_mesa': cajas_mesa.to_dict('records') if not cajas_mesa.empty else []
        }
        
        return reporte
    except Exception as e:
        return None

def registrar_cierre_dia(fecha, cerrado_por):
    """Registra el cierre del día"""
    try:
        # Verificar si ya está cerrado
        existente = supabase.table('cierres_dia').select('id').eq('fecha', fecha.isoformat()).execute()
        if existente.data:
            return False, "❌ Este día ya fue cerrado anteriormente"
        
        reporte = generar_reporte_cierre_dia(fecha)
        
        if reporte:
            supabase.table('cierres_dia').insert({
                'fecha': fecha.isoformat(),
                'cerrado_por': cerrado_por,
                'reporte': reporte
            }).execute()
            
            invalidar_cache()
            return True, "✅ Cierre de día registrado exitosamente"
        
        return False, "❌ Error al generar el reporte"
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

def get_cierres_dia():
    """Obtiene el historial de cierres de día"""
    try:
        result = supabase.table('cierres_dia').select('*').order('fecha', desc=True).execute()
        data = []
        for row in result.data:
            data.append({
                'fecha': row['fecha'],
                'cerrado_por': row['cerrado_por'],
                'created_at': row['created_at']
            })
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

# ==========================================
# FUNCIONES DE GESTIÓN DE USUARIOS (ADMIN)
# ==========================================

def get_all_users():
    """Obtiene todos los usuarios del sistema"""
    try:
        result = supabase.table('perfiles_usuario').select('*').execute()
        return pd.DataFrame(result.data) if result.data else pd.DataFrame()
    except:
        return pd.DataFrame()

def update_user_permissions(user_id, rol, permisos, invernaderos_asignados):
    """Actualiza permisos de un usuario"""
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

def update_system_config(clave, valor):
    """Actualiza configuración del sistema"""
    try:
        supabase.table('configuracion_sistema').update({'valor': valor}).eq('clave', clave).execute()
        invalidar_cache()
        return True
    except:
        return False

# ==========================================
# FUNCIONES DE QR
# ==========================================

def generar_qr_trabajador(id_trabajador, nombre, url_base="https://tu-app.streamlit.app"):
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

def procesar_qr_data(qr_data):
    try:
        id_match = re.search(r'[?&]id=([^&]+)', qr_data)
        nombre_match = re.search(r'[?&]nombre=([^&]+)', qr_data)
        
        if id_match and nombre_match:
            return id_match.group(1), nombre_match.group(1).replace('%20', ' ')
        return None, None
    except:
        return None, None

def registrar_escaneo_qr(id_trabajador, nombre_trabajador, tipo_evento="asistencia", invernadero_id=None):
    try:
        fecha_actual = datetime.now().strftime("%d/%m/%Y")
        hora_actual = datetime.now().strftime("%H:%M:%S")
        
        supabase.table('registros_escaneo').insert({
            'id_trabajador': str(id_trabajador),
            'nombre_trabajador': nombre_trabajador,
            'fecha_escaneo': fecha_actual,
            'hora_escaneo': hora_actual,
            'tipo_evento': tipo_evento,
            'invernadero_id': invernadero_id
        }).execute()
        
        return True
    except:
        return False

# ==========================================
# FUNCIONES DE DASHBOARD
# ==========================================

def get_dashboard_stats(fecha_inicio=None, fecha_fin=None, invernadero_id=None):
    try:
        # Cosechas
        query_cosechas = supabase.table('cosechas').select('*')
        if fecha_inicio:
            query_cosechas = query_cosechas.gte('fecha', fecha_inicio.isoformat())
        if fecha_fin:
            query_cosechas = query_cosechas.lte('fecha', fecha_fin.isoformat())
        if invernadero_id:
            query_cosechas = query_cosechas.eq('invernadero_id', invernadero_id)
        cosechas = query_cosechas.execute()
        
        # Envíos
        query_envios = supabase.table('envios_enfriado').select('*')
        if fecha_inicio:
            query_envios = query_envios.gte('fecha', fecha_inicio.isoformat())
        if fecha_fin:
            query_envios = query_envios.lte('fecha', fecha_fin.isoformat())
        if invernadero_id:
            query_envios = query_envios.eq('invernadero_id', invernadero_id)
        envios = query_envios.execute()
        
        # Merma
        query_merma = supabase.table('merma').select('*')
        if fecha_inicio:
            query_merma = query_merma.gte('fecha', fecha_inicio.isoformat())
        if fecha_fin:
            query_merma = query_merma.lte('fecha', fecha_fin.isoformat())
        if invernadero_id:
            query_merma = query_merma.eq('invernadero_id', invernadero_id)
        merma = query_merma.execute()
        
        # Trabajadores activos
        trabajadores = supabase.table('trabajadores').select('id', count='exact').eq('estatus', 'activo').execute()
        
        total_cajas = sum(row.get('numero_cajas', 0) for row in cosechas.data)
        total_envios = sum(row.get('cantidad_cajas', 0) for row in envios.data)
        total_merma = sum(row.get('kilos_merma', 0) for row in merma.data)
        
        return {
            'total_cajas': total_cajas,
            'total_envios': total_envios,
            'total_merma': total_merma,
            'total_trabajadores': trabajadores.count if trabajadores.count else 0,
            'porcentaje_merma': (total_merma / total_cajas * 100) if total_cajas > 0 else 0
        }
    except:
        return {
            'total_cajas': 0,
            'total_envios': 0,
            'total_merma': 0,
            'total_trabajadores': 0,
            'porcentaje_merma': 0
        }

# ==========================================
# INTERFACES DE USUARIO
# ==========================================

def mostrar_gestion_personal():
    st.header("👥 Gestión de Personal")
    
    tab1, tab2, tab3 = st.tabs(["➕ Alta", "🔍 Buscar/Editar", "📊 Reportes"])
    
    with tab1:
        with st.form("form_alta"):
            col1, col2 = st.columns(2)
            
            with col1:
                apellido_paterno = st.text_input("Apellido Paterno *")
                nombre = st.text_input("Nombre *")
                telefono = st.text_input("Teléfono")
            
            with col2:
                apellido_materno = st.text_input("Apellido Materno")
                correo = st.text_input("Correo Electrónico")
                fecha_alta = st.date_input("Fecha de Alta", datetime.now())
            
            col3, col4, col5 = st.columns(3)
            with col3:
                departamentos = get_departamentos()
                depto = st.selectbox("Departamento *", [d[1] for d in departamentos] if departamentos else ["Sin datos"])
            with col4:
                subdepartamentos = get_subdepartamentos()
                subdepto = st.selectbox("Subdepartamento *", [s[1] for s in subdepartamentos] if subdepartamentos else ["Sin datos"])
            with col5:
                tipo_nomina = st.selectbox("Tipo Nómina", ["especial", "imss"])
            
            puestos = get_puestos()
            puesto = st.selectbox("Puesto *", [p[1] for p in puestos] if puestos else ["Sin datos"])
            
            if st.form_submit_button("💾 Guardar Trabajador", type="primary"):
                if apellido_paterno and nombre and depto != "Sin datos":
                    data = {
                        "ap": apellido_paterno.upper(),
                        "am": apellido_materno.upper() if apellido_materno else None,
                        "nom": nombre.upper(),
                        "cor": correo if correo else None,
                        "tel": telefono if telefono else None,
                        "fa": fecha_alta,
                        "departamento": depto,
                        "subdepartamento": subdepto,
                        "tn": tipo_nomina,
                        "puesto": puesto
                    }
                    success, msg = add_worker(data)
                    if success:
                        st.success(msg)
                        st.balloons()
                    else:
                        st.error(msg)
                else:
                    st.error("Complete campos obligatorios")
    
    with tab2:
        search_term = st.text_input("Buscar por nombre o apellido")
        estatus_filter = st.selectbox("Estatus", ["todos", "activo", "baja"])
        
        if st.button("🔍 Buscar"):
            results = search_workers(search_term, estatus_filter)
            if not results.empty:
                for _, row in results.iterrows():
                    with st.expander(f"{row['apellido_paterno']} {row['apellido_materno']}, {row['nombre']}"):
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.write(f"**ID:** {row['id']}")
                            st.write(f"**Email:** {row['correo']}")
                            st.write(f"**Teléfono:** {row['telefono']}")
                        with col2:
                            st.write(f"**Departamento:** {row['departamento']}")
                            st.write(f"**Puesto:** {row['puesto']}")
                            st.write(f"**Estatus:** {row['estatus']}")
                        with col3:
                            if row['estatus'] == 'activo':
                                if st.button("🚫 Dar Baja", key=f"baja_{row['id']}"):
                                    fecha_baja = st.date_input("Fecha de baja", datetime.now(), key=f"fecha_baja_{row['id']}")
                                    if st.button("Confirmar", key=f"conf_baja_{row['id']}"):
                                        success, msg = dar_baja(row['id'], fecha_baja)
                                        if success:
                                            st.success(msg)
                                            st.rerun()
                            else:
                                if st.button("🔄 Reactivar", key=f"reactivar_{row['id']}"):
                                    success, msg = reactivar_trabajador(row['id'])
                                    if success:
                                        st.success(msg)
                                        st.rerun()
            else:
                st.info("No se encontraron resultados")

def mostrar_registro_cosecha():
    st.header("🌾 Registro de Cosecha")
    
    registro_manual = get_configuracion_sistema('registro_manual_cosecha')
    
    tab1, tab2 = st.tabs(["📷 Escanear QR", "📝 Registrar Manual" if registro_manual else "📝 Registrar Manual (Deshabilitado)"])
    
    with tab1:
        st.markdown("### 📷 Escaneo con Cámara")
        camera_image = st.camera_input("Enfoca el código QR del trabajador")
        
        if camera_image:
            image = Image.open(camera_image)
            img_array = np.array(image)
            qr_codes = decode(img_array)
            
            if qr_codes:
                qr_data = qr_codes[0].data.decode('utf-8')
                id_trabajador, nombre = procesar_qr_data(qr_data)
                
                if id_trabajador and nombre:
                    st.success(f"✅ QR detectado: {nombre}")
                    
                    invernaderos = get_invernaderos_usuario()
                    if invernaderos:
                        invernadero = st.selectbox("Invernadero", invernaderos, format_func=lambda x: f"{x[1]} - {x[2]}")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            tipo_cosecha = st.radio("Tipo", ["Nacional", "Exportación"], horizontal=True)
                            if tipo_cosecha == "Nacional":
                                calidad = st.selectbox("Calidad", ["Salmon", "Sobretono"])
                                presentacion = "6 oz"
                                st.info("Presentación automática: 6 oz")
                            else:
                                presentacion = st.selectbox("Presentación", ["6 oz", "12 oz"])
                                calidad = None
                        
                        with col2:
                            cantidad_clams = st.number_input("Cantidad de Clams", min_value=0.0, step=1.0)
                            merma_kilos = st.number_input("Merma (kilos)", min_value=0.0, step=0.5)
                            observaciones = st.text_area("Observaciones")
                            
                            if presentacion == "12 oz":
                                cajas = cantidad_clams / 6 if cantidad_clams > 0 else 0
                            else:
                                cajas = cantidad_clams / 12 if cantidad_clams > 0 else 0
                            st.metric("Cajas a registrar", f"{cajas:.2f}")
                        
                        if st.button("💾 Guardar Cosecha", type="primary"):
                            if cantidad_clams > 0:
                                data = {
                                    'fecha': datetime.now().date(),
                                    'dia': datetime.now().strftime('%A'),
                                    'semana': datetime.now().isocalendar()[1],
                                    'trabajador_id': int(id_trabajador),
                                    'invernadero_id': invernadero[0],
                                    'tipo_cosecha': tipo_cosecha,
                                    'calidad': calidad,
                                    'presentacion': presentacion,
                                    'cantidad_clams': cantidad_clams,
                                    'merma_kilos': merma_kilos,
                                    'observaciones': observaciones
                                }
                                success, msg = guardar_cosecha(data)
                                if success:
                                    st.success(msg)
                                    st.balloons()
                                    registrar_escaneo_qr(id_trabajador, nombre, "cosecha", invernadero[0])
                                else:
                                    st.error(msg)
                            else:
                                st.error("Ingrese cantidad de clams")
                else:
                    st.error("QR no válido")
            else:
                st.warning("No se detectó QR. Enfoca bien el código.")
    
    if registro_manual:
        with tab2:
            st.markdown("### 📝 Registro Manual")
            
            trabajadores = get_all_workers()
            if not trabajadores.empty:
                trabajador = st.selectbox("Trabajador", trabajadores.apply(lambda x: f"{x['id']} - {x['nombre']} {x['apellido_paterno']}", axis=1))
                trabajador_id = int(trabajador.split(' - ')[0]) if trabajador else None
                
                invernaderos = get_invernaderos_usuario()
                if invernaderos:
                    invernadero = st.selectbox("Invernadero", invernaderos, format_func=lambda x: f"{x[1]} - {x[2]}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        tipo_cosecha = st.radio("Tipo", ["Nacional", "Exportación"], horizontal=True)
                        if tipo_cosecha == "Nacional":
                            calidad = st.selectbox("Calidad", ["Salmon", "Sobretono"])
                            presentacion = "6 oz"
                        else:
                            presentacion = st.selectbox("Presentación", ["6 oz", "12 oz"])
                            calidad = None
                    
                    with col2:
                        cantidad_clams = st.number_input("Cantidad de Clams", min_value=0.0, step=1.0)
                        merma_kilos = st.number_input("Merma (kilos)", min_value=0.0, step=0.5)
                        observaciones = st.text_area("Observaciones")
                        
                        if presentacion == "12 oz":
                            cajas = cantidad_clams / 6 if cantidad_clams > 0 else 0
                        else:
                            cajas = cantidad_clams / 12 if cantidad_clams > 0 else 0
                        st.metric("Cajas", f"{cajas:.2f}")
                    
                    if st.button("💾 Guardar", type="primary"):
                        if trabajador_id and cantidad_clams > 0:
                            data = {
                                'fecha': datetime.now().date(),
                                'dia': datetime.now().strftime('%A'),
                                'semana': datetime.now().isocalendar()[1],
                                'trabajador_id': trabajador_id,
                                'invernadero_id': invernadero[0],
                                'tipo_cosecha': tipo_cosecha,
                                'calidad': calidad,
                                'presentacion': presentacion,
                                'cantidad_clams': cantidad_clams,
                                'merma_kilos': merma_kilos,
                                'observaciones': observaciones
                            }
                            success, msg = guardar_cosecha(data)
                            if success:
                                st.success(msg)
                                st.balloons()
                            else:
                                st.error(msg)
                        else:
                            st.error("Complete todos los campos")
    else:
        with tab2:
            st.warning("⚠️ El registro manual de cosecha está deshabilitado por el administrador")

def mostrar_control_asistencia():
    st.header("🕐 Control de Asistencia")
    
    registro_manual = get_configuracion_sistema('registro_manual_asistencia')
    
    tab1, tab2 = st.tabs(["📷 Escanear QR", "📝 Registrar Manual" if registro_manual else "📝 Registrar Manual (Deshabilitado)"])
    
    with tab1:
        st.markdown("### 📷 Escaneo con Cámara")
        camera_image = st.camera_input("Enfoca el código QR del trabajador")
        
        if camera_image:
            image = Image.open(camera_image)
            img_array = np.array(image)
            qr_codes = decode(img_array)
            
            if qr_codes:
                qr_data = qr_codes[0].data.decode('utf-8')
                id_trabajador, nombre = procesar_qr_data(qr_data)
                
                if id_trabajador and nombre:
                    st.success(f"✅ QR detectado: {nombre}")
                    
                    estado_actual = get_estado_asistencia_actual(int(id_trabajador))
                    
                    if estado_actual:
                        st.info(f"Estado actual: {estado_actual['estado']} - Entrada: {estado_actual.get('hora_entrada', 'N/A')}")
                    
                    tipo_evento = st.radio(
                        "Tipo de evento",
                        ["entrada_invernadero", "salida_invernadero"],
                        format_func=lambda x: "🚪 Entrada a Invernadero" if x == "entrada_invernadero" else "🚪 Salida de Invernadero"
                    )
                    
                    invernadero_id = None
                    if tipo_evento == "entrada_invernadero":
                        invernaderos = get_invernaderos_usuario()
                        if invernaderos:
                            invernadero = st.selectbox("Invernadero", invernaderos, format_func=lambda x: f"{x[1]} - {x[2]}")
                            invernadero_id = invernadero[0]
                        else:
                            st.error("No tienes invernaderos asignados")
                    
                    if st.button("✅ Registrar", type="primary"):
                        if tipo_evento == "entrada_invernadero" and not invernadero_id:
                            st.error("Seleccione un invernadero")
                        else:
                            success, msg = registrar_evento_asistencia(int(id_trabajador), invernadero_id, tipo_evento)
                            if success:
                                st.success(msg)
                                st.balloons()
                                registrar_escaneo_qr(id_trabajador, nombre, tipo_evento, invernadero_id)
                            else:
                                st.error(msg)
                else:
                    st.error("QR no válido")
            else:
                st.warning("No se detectó QR")
    
    if registro_manual:
        with tab2:
            st.markdown("### 📝 Registro Manual")
            
            trabajadores = get_all_workers()
            if not trabajadores.empty:
                trabajador = st.selectbox("Trabajador", trabajadores.apply(lambda x: f"{x['id']} - {x['nombre']} {x['apellido_paterno']}", axis=1))
                trabajador_id = int(trabajador.split(' - ')[0]) if trabajador else None
                
                estado_actual = get_estado_asistencia_actual(trabajador_id) if trabajador_id else None
                
                if estado_actual:
                    st.info(f"Estado: {estado_actual['estado']} - Entrada: {estado_actual.get('hora_entrada', 'N/A')}")
                
                tipo_evento = st.radio(
                    "Tipo de evento",
                    ["entrada_invernadero", "salida_invernadero"],
                    format_func=lambda x: "🚪 Entrada" if x == "entrada_invernadero" else "🚪 Salida"
                )
                
                invernadero_id = None
                if tipo_evento == "entrada_invernadero":
                    invernaderos = get_invernaderos_usuario()
                    if invernaderos:
                        invernadero = st.selectbox("Invernadero", invernaderos, format_func=lambda x: f"{x[1]} - {x[2]}")
                        invernadero_id = invernadero[0]
                
                if st.button("✅ Registrar", type="primary"):
                    if trabajador_id:
                        success, msg = registrar_evento_asistencia(trabajador_id, invernadero_id, tipo_evento)
                        if success:
                            st.success(msg)
                            st.balloons()
                        else:
                            st.error(msg)
                    else:
                        st.error("Seleccione trabajador")
    else:
        with tab2:
            st.warning("⚠️ El registro manual de asistencia está deshabilitado por el administrador")
    
    # Historial de asistencia
    st.markdown("---")
    st.subheader("📋 Historial de Asistencia")
    
    col1, col2 = st.columns(2)
    with col1:
        fecha_inicio = st.date_input("Fecha inicio", datetime.now().date() - timedelta(days=30))
    with col2:
        fecha_fin = st.date_input("Fecha fin", datetime.now().date())
    
    if st.button("🔍 Buscar Historial"):
        historial = get_registros_asistencia({'fecha_inicio': fecha_inicio, 'fecha_fin': fecha_fin})
        if not historial.empty:
            st.dataframe(historial, use_container_width=True)
            output = export_to_excel(historial, "Historial_Asistencia")
            st.download_button("📥 Exportar a Excel", data=output, file_name=f"asistencia_{datetime.now().date()}.xlsx")
        else:
            st.info("No hay registros")

def mostrar_envios_enfriado():
    st.header("❄️ Gestión de Envíos a Enfriado")
    
    tab1, tab2, tab3, tab4 = st.tabs(["📦 Registrar Envío", "⚖️ Registrar Pesaje", "📊 Dashboard", "📋 Historial"])
    
    with tab1:
        st.subheader("Registrar Envío de Cajas")
        
        fecha_actual = datetime.now()
        st.markdown(f"""
        <div style="display: flex; gap: 10px; margin-bottom: 20px;">
            <div class="date-card"><div>📅 FECHA</div><div style="font-size:20px;">{fecha_actual.strftime('%d/%m/%Y')}</div></div>
            <div class="time-card"><div>⏰ HORA</div><div style="font-size:20px;">{fecha_actual.strftime('%H:%M')}</div></div>
            <div class="week-card"><div>📆 SEMANA</div><div style="font-size:20px;">{fecha_actual.isocalendar()[1]}</div></div>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            invernaderos = get_invernaderos_usuario()
            if invernaderos:
                invernadero = st.selectbox("Invernadero de origen", invernaderos, format_func=lambda x: f"{x[1]} - {x[2]}")
                invernadero_id = invernadero[0]
            else:
                st.error("No hay invernaderos asignados")
                invernadero_id = None
        
        with col2:
            if invernadero_id:
                detalle_cajas = get_detalle_cajas_por_invernadero_presentacion(invernadero_id)
                total_cajas = detalle_cajas.get('6 oz', 0) + detalle_cajas.get('12 oz', 0)
                st.info(f"📦 Cajas disponibles: {total_cajas:.0f} (6 oz: {detalle_cajas.get('6 oz', 0):.0f}, 12 oz: {detalle_cajas.get('12 oz', 0):.0f})")
        
        col1, col2 = st.columns(2)
        
        with col1:
            trabajadores = get_all_workers()
            supervisores = trabajadores[trabajadores['puesto'].str.contains('Supervisor', case=False, na=False)] if not trabajadores.empty else pd.DataFrame()
            
            if not supervisores.empty:
                supervisor = st.selectbox("Supervisor que entrega", supervisores.apply(lambda x: f"{x['id']} - {x['nombre']} {x['apellido_paterno']}", axis=1))
                supervisor_id = int(supervisor.split(' - ')[0]) if supervisor else None
            else:
                st.warning("No hay supervisores registrados")
                supervisor_id = None
        
        with col2:
            recolectores = get_recolectores()
            if recolectores:
                recolector = st.selectbox("Recolector (quien lleva las cajas)", recolectores, format_func=lambda x: x[1])
                recolector_id = recolector[0] if recolector else None
            else:
                st.warning("No hay recolectores registrados")
                recolector_id = None
        
        col1, col2, col3 = st.columns(3)
        with col1:
            tipo_envio = st.selectbox("Tipo de envío", ["Nacional", "Exportación"])
        with col2:
            presentacion = st.selectbox("Presentación", ["6 oz", "12 oz"])
        with col3:
            cantidad_cajas = st.number_input("Cantidad de cajas", min_value=0.0, step=1.0)
        
        lote = st.text_input("Número de lote (opcional)")
        observaciones = st.text_area("Observaciones")
        
        if st.button("✅ Registrar Envío", type="primary"):
            if invernadero_id and supervisor_id and recolector_id and cantidad_cajas > 0:
                detalle_cajas = get_detalle_cajas_por_invernadero_presentacion(invernadero_id)
                disponibles = detalle_cajas.get(presentacion, 0)
                
                if cantidad_cajas <= disponibles:
                    success, msg = registrar_envio_enfriado(invernadero_id, cantidad_cajas, supervisor_id, recolector_id, tipo_envio, presentacion, lote, observaciones)
                    if success:
                        st.success(msg)
                        st.balloons()
                    else:
                        st.error(msg)
                else:
                    st.error(f"No hay suficientes cajas de {presentacion}. Disponibles: {disponibles:.0f}")
            else:
                st.error("Complete todos los campos")
    
    with tab2:
        st.subheader("⚖️ Registrar Pesaje de Cajas")
        
        envios_pendientes = get_envios_enfriado(fecha_inicio=datetime.now().date(), fecha_fin=datetime.now().date())
        
        if not envios_pendientes.empty:
            envio = st.selectbox("Seleccionar envío a pesar", envios_pendientes.apply(lambda x: f"ID:{x['id']} - {x['invernadero']} - {x['cantidad_cajas']} cajas", axis=1))
            envio_id = int(envio.split(' - ')[0].replace('ID:', '')) if envio else None
            
            if envio_id:
                envio_data = envios_pendientes[envios_pendientes['id'] == envio_id].iloc[0]
                
                st.info(f"Envío: {envio_data['cantidad_cajas']} cajas de {envio_data['presentacion']} desde {envio_data['invernadero']}")
                
                col1, col2 = st.columns(2)
                with col1:
                    cantidad_pesadas = st.number_input("Cantidad de cajas pesadas", min_value=0.0, step=1.0, value=float(envio_data['cantidad_cajas']))
                with col2:
                    cajas_recibidas = st.number_input("Cajas recibidas en frío", min_value=0.0, step=1.0, value=float(envio_data['cantidad_cajas']))
                
                nota = st.text_area("Nota (si hay diferencia)")
                
                trabajadores = get_all_workers()
                pesadores = trabajadores[trabajadores['puesto'].str.contains('Pesador', case=False, na=False)] if not trabajadores.empty else pd.DataFrame()
                
                if not pesadores.empty:
                    pesador = st.selectbox("Pesador", pesadores.apply(lambda x: f"{x['id']} - {x['nombre']} {x['apellido_paterno']}", axis=1))
                    pesador_id = int(pesador.split(' - ')[0]) if pesador else None
                else:
                    pesador_id = None
                
                if st.button("✅ Registrar Pesaje", type="primary"):
                    if pesador_id:
                        success, msg = registrar_pesaje_cajas(envio_id, envio_data['invernadero_id'], pesador_id, envio_data['presentacion'], cantidad_pesadas, cajas_recibidas, nota)
                        if success:
                            st.success(msg)
                            st.balloons()
                        else:
                            st.error(msg)
                    else:
                        st.error("Seleccione un pesador")
        else:
            st.info("No hay envíos pendientes de pesar hoy")
    
    with tab3:
        st.subheader("📊 Dashboard de Envíos")
        
        col1, col2 = st.columns(2)
        with col1:
            fecha_inicio = st.date_input("Fecha inicio", datetime.now().date() - timedelta(days=30))
        with col2:
            fecha_fin = st.date_input("Fecha fin", datetime.now().date())
        
        envios = get_envios_enfriado(fecha_inicio, fecha_fin)
        pesajes = get_pesajes(fecha_inicio, fecha_fin)
        
        if not envios.empty:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Envíos", len(envios))
            with col2:
                st.metric("Total Cajas", f"{envios['cantidad_cajas'].sum():,.0f}")
            with col3:
                st.metric("Promedio por Envío", f"{envios['cantidad_cajas'].mean():.1f}")
            with col4:
                if not pesajes.empty:
                    diferencias = pesajes['diferencia'].sum()
                    st.metric("Diferencia Total", f"{diferencias:+,.0f}", delta="cajas" if diferencias != 0 else None)
            
            fig = px.bar(envios, x='fecha', y='cantidad_cajas', color='presentacion', title='Envíos por Día')
            st.plotly_chart(fig, use_container_width=True)
    
    with tab4:
        st.subheader("📋 Historial de Envíos")
        
        col1, col2 = st.columns(2)
        with col1:
            fecha_hist_inicio = st.date_input("Fecha inicio", datetime.now().date() - timedelta(days=30), key="hist_inicio")
        with col2:
            fecha_hist_fin = st.date_input("Fecha fin", datetime.now().date(), key="hist_fin")
        
        envios_hist = get_envios_enfriado(fecha_hist_inicio, fecha_hist_fin)
        if not envios_hist.empty:
            st.dataframe(envios_hist, use_container_width=True)
            output = export_to_excel(envios_hist, "Envios")
            st.download_button("📥 Exportar a Excel", data=output, file_name=f"envios_{datetime.now().date()}.xlsx")
        else:
            st.info("No hay registros")

def get_detalle_cajas_por_invernadero_presentacion(invernadero_id):
    try:
        cosechas = supabase.table('cosechas').select('presentacion, numero_cajas, cajas_enviadas')\
            .eq('invernadero_id', invernadero_id).execute()
        
        resultados = {'6 oz': 0, '12 oz': 0}
        for row in cosechas.data:
            disponibles = row['numero_cajas'] - row['cajas_enviadas']
            if row['presentacion'] in resultados:
                resultados[row['presentacion']] += disponibles
        return resultados
    except:
        return {'6 oz': 0, '12 oz': 0}

def mostrar_cajas_mesa():
    st.header("📦 Cajas en Mesa")
    
    tab1, tab2 = st.tabs(["📝 Registrar Cajas", "🆘 Solicitudes de Apoyo"])
    
    with tab1:
        st.subheader("Registrar Cajas en Mesa")
        
        invernaderos = get_invernaderos_usuario()
        if invernaderos:
            invernadero = st.selectbox("Invernadero", invernaderos, format_func=lambda x: f"{x[1]} - {x[2]}")
            invernadero_id = invernadero[0]
        else:
            invernadero_id = None
        
        trabajadores = get_all_workers()
        if not trabajadores.empty:
            trabajador = st.selectbox("Trabajador", trabajadores.apply(lambda x: f"{x['id']} - {x['nombre']} {x['apellido_paterno']}", axis=1))
            trabajador_id = int(trabajador.split(' - ')[0]) if trabajador else None
        else:
            trabajador_id = None
        
        col1, col2 = st.columns(2)
        with col1:
            presentacion = st.selectbox("Presentación", ["6 oz", "12 oz"])
            cantidad_cajas = st.number_input("Cantidad de cajas", min_value=0.0, step=1.0)
        with col2:
            solicitando_apoyo = st.checkbox("Solicitar apoyo")
            observaciones = st.text_area("Observaciones")
        
        if st.button("✅ Registrar", type="primary"):
            if invernadero_id and trabajador_id and cantidad_cajas > 0:
                success, msg = registrar_cajas_mesa(invernadero_id, trabajador_id, cantidad_cajas, presentacion, solicitando_apoyo, observaciones)
                if success:
                    st.success(msg)
                    st.balloons()
                else:
                    st.error(msg)
            else:
                st.error("Complete todos los campos")
    
    with tab2:
        st.subheader("🆘 Solicitudes de Apoyo Pendientes")
        
        cajas_pendientes = get_cajas_mesa(solo_pendientes=True)
        
        if not cajas_pendientes.empty:
            solicitudes = cajas_pendientes[cajas_pendientes['solicita_apoyo'] == True]
            if not solicitudes.empty:
                for _, row in solicitudes.iterrows():
                    with st.expander(f"{row['invernadero']} - {row['cantidad_cajas']} cajas de {row['presentacion']}"):
                        st.write(f"**Trabajador:** {row['trabajador']}")
                        st.write(f"**Hora:** {row['hora']}")
                        st.write(f"**Observaciones:** {row['observaciones']}")
                        
                        if st.button("✅ Marcar como Atendido", key=f"atender_{row['id']}"):
                            success, msg = marcar_atendido_caja_mesa(row['id'], st.session_state.get('user_nombre', 'Sistema'))
                            if success:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
            else:
                st.info("No hay solicitudes de apoyo pendientes")
            
            st.markdown("---")
            st.subheader("Registros del día")
            st.dataframe(cajas_pendientes, use_container_width=True)
        else:
            st.info("No hay registros de cajas en mesa hoy")

def mostrar_gestion_merma():
    st.header("🗑️ Gestión de Merma")
    
    tab1, tab2, tab3 = st.tabs(["📝 Registrar Merma", "📊 Dashboard", "📋 Historial"])
    
    with tab1:
        st.subheader("Registrar Merma")
        
        fecha_actual = datetime.now()
        st.markdown(f"""
        <div style="display: flex; gap: 10px; margin-bottom: 20px;">
            <div class="date-card"><div>📅 FECHA</div><div style="font-size:20px;">{fecha_actual.strftime('%d/%m/%Y')}</div></div>
            <div class="time-card"><div>⏰ HORA</div><div style="font-size:20px;">{fecha_actual.strftime('%H:%M')}</div></div>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            invernaderos = get_invernaderos_usuario()
            if invernaderos:
                invernadero = st.selectbox("Invernadero", invernaderos, format_func=lambda x: f"{x[1]} - {x[2]}")
                invernadero_id = invernadero[0]
            else:
                invernadero_id = None
        
        with col2:
            supervisor = st.text_input("Nombre del Supervisor")
        
        kilos_merma = st.number_input("Kilos de Merma", min_value=0.0, step=0.5)
        tipo_merma = st.selectbox("Tipo de Merma", ["Fruta dañada", "Fruta sobremadura", "Fruta con defectos", "Contaminación", "Manejo inadecuado", "Temperatura", "Plagas", "Otra"])
        observaciones = st.text_area("Observaciones")
        registrado_por = st.text_input("Registrado por", value=st.session_state.get('user_nombre', ''))
        
        if st.button("✅ Registrar Merma", type="primary"):
            if invernadero_id and supervisor and kilos_merma > 0 and registrado_por:
                success, msg = registrar_merma(invernadero_id, supervisor, kilos_merma, tipo_merma, observaciones, registrado_por)
                if success:
                    st.success(msg)
                    st.balloons()
                else:
                    st.error(msg)
            else:
                st.error("Complete todos los campos")
    
    with tab2:
        st.subheader("Dashboard de Merma")
        
        col1, col2 = st.columns(2)
        with col1:
            fecha_inicio = st.date_input("Fecha inicio", datetime.now().date() - timedelta(days=30), key="merma_inicio")
        with col2:
            fecha_fin = st.date_input("Fecha fin", datetime.now().date(), key="merma_fin")
        
        merma = get_merma(fecha_inicio, fecha_fin)
        
        if not merma.empty:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Kilos", f"{merma['kilos'].sum():.2f} kg")
            with col2:
                st.metric("Total Registros", len(merma))
            with col3:
                st.metric("Promedio por Registro", f"{merma['kilos'].mean():.2f} kg")
            with col4:
                top_inv = merma.groupby('invernadero')['kilos'].sum().sort_values(ascending=False)
                if not top_inv.empty:
                    st.metric("Mayor Merma", top_inv.index[0])
            
            fig1 = px.bar(merma.groupby('fecha')['kilos'].sum().reset_index(), x='fecha', y='kilos', title='Merma Diaria')
            st.plotly_chart(fig1, use_container_width=True)
            
            fig2 = px.pie(merma, values='kilos', names='tipo', title='Merma por Tipo')
            st.plotly_chart(fig2, use_container_width=True)
    
    with tab3:
        st.subheader("Historial de Merma")
        
        col1, col2 = st.columns(2)
        with col1:
            fecha_hist_inicio = st.date_input("Fecha inicio", datetime.now().date() - timedelta(days=30), key="merma_hist_inicio")
        with col2:
            fecha_hist_fin = st.date_input("Fecha fin", datetime.now().date(), key="merma_hist_fin")
        
        merma_hist = get_merma(fecha_hist_inicio, fecha_hist_fin)
        if not merma_hist.empty:
            st.dataframe(merma_hist, use_container_width=True)
            output = export_to_excel(merma_hist, "Merma")
            st.download_button("📥 Exportar a Excel", data=output, file_name=f"merma_{datetime.now().date()}.xlsx")

def mostrar_avance_cosecha():
    st.header("📊 Avance de Cosecha")
    
    tab1, tab2 = st.tabs(["📝 Registrar Avance", "📊 Historial"])
    
    with tab1:
        st.subheader("Registrar Avance Diario")
        
        fecha_actual = datetime.now()
        st.markdown(f"""
        <div style="display: flex; gap: 10px; margin-bottom: 20px;">
            <div class="date-card"><div>📅 FECHA</div><div style="font-size:20px;">{fecha_actual.strftime('%d/%m/%Y')}</div></div>
            <div class="time-card"><div>⏰ HORA</div><div style="font-size:20px;">{fecha_actual.strftime('%H:%M')}</div></div>
            <div class="week-card"><div>📆 SEMANA</div><div style="font-size:20px;">{fecha_actual.isocalendar()[1]}</div></div>
        </div>
        """, unsafe_allow_html=True)
        
        invernaderos = get_invernaderos_usuario()
        if invernaderos:
            invernadero = st.selectbox("Invernadero", invernaderos, format_func=lambda x: f"{x[1]} - {x[2]}")
            invernadero_id = invernadero[0]
            invernadero_nombre = invernadero[1]
            lineas_totales = get_lineas_totales_invernadero(invernadero_id)
            
            ultimo_avance = get_ultimo_avance_dia(invernadero_id)
            
            if ultimo_avance:
                st.info(f"Avance actual: {ultimo_avance['lineas_cosechadas']} de {lineas_totales} líneas ({ultimo_avance['porcentaje']:.1f}%)")
            
            col1, col2 = st.columns(2)
            with col1:
                lineas_cosechadas = st.number_input("Líneas cosechadas", min_value=0, max_value=lineas_totales, value=ultimo_avance['lineas_cosechadas'] if ultimo_avance else 0)
            with col2:
                turno = st.selectbox("Turno", ["Matutino", "Vespertino", "Nocturno"])
            
            supervisor = st.text_input("Supervisor")
            observaciones = st.text_area("Observaciones")
            
            if st.button("✅ Registrar Avance", type="primary"):
                if supervisor:
                    if lineas_cosechadas >= (ultimo_avance['lineas_cosechadas'] if ultimo_avance else 0):
                        success, msg = registrar_avance_cosecha(invernadero_id, lineas_cosechadas, supervisor, observaciones, turno)
                        if success:
                            st.success(msg)
                            st.balloons()
                        else:
                            st.error(msg)
                    else:
                        st.error("El avance no puede disminuir")
                else:
                    st.error("Ingrese nombre del supervisor")
        else:
            st.error("No tienes invernaderos asignados")
    
    with tab2:
        st.subheader("Historial de Avance")
        
        col1, col2 = st.columns(2)
        with col1:
            fecha_hist_inicio = st.date_input("Fecha inicio", datetime.now().date() - timedelta(days=30), key="avance_hist_inicio")
        with col2:
            fecha_hist_fin = st.date_input("Fecha fin", datetime.now().date(), key="avance_hist_fin")
        
        avance_hist = get_avance_historico(fecha_hist_inicio, fecha_hist_fin)
        if not avance_hist.empty:
            st.dataframe(avance_hist, use_container_width=True)
            
            fig = px.line(avance_hist, x='fecha', y='porcentaje', color='invernadero', title='Evolución del Avance')
            st.plotly_chart(fig, use_container_width=True)
            
            output = export_to_excel(avance_hist, "Avance_Cosecha")
            st.download_button("📥 Exportar a Excel", data=output, file_name=f"avance_{datetime.now().date()}.xlsx")

def mostrar_proyecciones():
    st.header("📈 Proyecciones de Cajas")
    
    tab1, tab2 = st.tabs(["📝 Registrar Proyección", "📊 Comparativa Real vs Proyectado"])
    
    with tab1:
        st.subheader("Registrar Proyección Semanal")
        
        semana_actual = datetime.now().isocalendar()[1]
        
        col1, col2 = st.columns(2)
        with col1:
            semana = st.number_input("Semana", min_value=1, max_value=52, value=semana_actual)
        with col2:
            cajas_proyectadas = st.number_input("Cajas proyectadas", min_value=0.0, step=50.0)
        
        registrado_por = st.text_input("Registrado por", value=st.session_state.get('user_nombre', ''))
        observaciones = st.text_area("Observaciones")
        
        if st.button("✅ Registrar Proyección", type="primary"):
            if registrado_por and cajas_proyectadas > 0:
                success, msg = registrar_proyeccion(semana, cajas_proyectadas, registrado_por, observaciones)
                if success:
                    st.success(msg)
                    st.balloons()
                else:
                    st.error(msg)
            else:
                st.error("Complete todos los campos")
    
    with tab2:
        st.subheader("Comparativa Real vs Proyectado")
        
        col1, col2 = st.columns(2)
        with col1:
            semana_inicio = st.number_input("Semana inicio", min_value=1, max_value=52, value=1)
        with col2:
            semana_fin = st.number_input("Semana fin", min_value=1, max_value=52, value=datetime.now().isocalendar()[1])
        
        comparativa = get_comparativa_proyeccion_real(semana_inicio, semana_fin)
        
        if not comparativa.empty:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Proyectado", f"{comparativa['proyectadas'].sum():,.0f}")
            with col2:
                st.metric("Total Real", f"{comparativa['reales'].sum():,.0f}")
            with col3:
                diff = comparativa['reales'].sum() - comparativa['proyectadas'].sum()
                st.metric("Diferencia", f"{diff:+,.0f}")
            with col4:
                porcentaje = (diff / comparativa['proyectadas'].sum() * 100) if comparativa['proyectadas'].sum() > 0 else 0
                st.metric("% Desviación", f"{porcentaje:+.1f}%")
            
            fig = go.Figure()
            fig.add_trace(go.Bar(x=comparativa['semana'], y=comparativa['proyectadas'], name='Proyectado', marker_color='#3498db'))
            fig.add_trace(go.Bar(x=comparativa['semana'], y=comparativa['reales'], name='Real', marker_color='#2ecc71'))
            fig.update_layout(title='Comparativa Semanal', xaxis_title='Semana', yaxis_title='Cajas', barmode='group')
            st.plotly_chart(fig, use_container_width=True)
            
            output = export_to_excel(comparativa, "Comparativa")
            st.download_button("📥 Exportar a Excel", data=output, file_name=f"comparativa_{datetime.now().date()}.xlsx")
        else:
            st.info("No hay datos para mostrar")

def mostrar_cierre_dia():
    st.header("📅 Cierre de Día")
    
    tab1, tab2 = st.tabs(["🔒 Realizar Cierre", "📋 Historial de Cierres"])
    
    with tab1:
        st.subheader("Realizar Cierre del Día")
        
        fecha_cierre = st.date_input("Fecha a cerrar", datetime.now().date())
        
        # Verificar si ya está cerrado
        cierres = get_cierres_dia()
        if not cierres.empty and fecha_cierre.isoformat() in cierres['fecha'].values:
            st.warning("⚠️ Esta fecha ya fue cerrada anteriormente")
        else:
            if st.button("🔒 Generar Reporte de Cierre", type="primary"):
                with st.spinner("Generando reporte..."):
                    reporte = generar_reporte_cierre_dia(fecha_cierre)
                    
                    if reporte:
                        st.success("Reporte generado exitosamente")
                        
                        st.subheader("📊 Resumen del Día")
                        col1, col2, col3, col4, col5 = st.columns(5)
                        with col1:
                            st.metric("Cajas Cosechadas", f"{reporte['resumen']['total_cajas_cosechadas']:.0f}")
                        with col2:
                            st.metric("Cajas Enviadas", f"{reporte['resumen']['total_cajas_enviadas']:.0f}")
                        with col3:
                            st.metric("Merma (kg)", f"{reporte['resumen']['total_merma_kilos']:.2f}")
                        with col4:
                            st.metric("Personal", reporte['resumen']['total_personal'])
                        with col5:
                            st.metric("Avance Promedio", f"{reporte['resumen']['promedio_avance']:.1f}%")
                        
                        if st.button("✅ Confirmar Cierre del Día"):
                            success, msg = registrar_cierre_dia(fecha_cierre, st.session_state.get('user_nombre', 'Sistema'))
                            if success:
                                st.success(msg)
                                st.balloons()
                            else:
                                st.error(msg)
                    else:
                        st.error("Error al generar el reporte")
    
    with tab2:
        st.subheader("Historial de Cierres")
        
        cierres = get_cierres_dia()
        if not cierres.empty:
            st.dataframe(cierres, use_container_width=True)
        else:
            st.info("No hay cierres registrados")

def mostrar_dashboard():
    st.header("📊 Dashboard General")
    
    # Sidebar de filtros
    with st.sidebar:
        st.markdown("### 📅 Filtros")
        fecha_inicio = st.date_input("Fecha inicio", datetime.now().date() - timedelta(days=30), key="dash_inicio")
        fecha_fin = st.date_input("Fecha fin", datetime.now().date(), key="dash_fin")
        
        invernaderos = get_invernaderos_usuario()
        invernadero_opciones = ["Todos"] + [inv[1] for inv in invernaderos]
        invernadero_seleccionado = st.selectbox("Invernadero", invernadero_opciones)
        
        invernadero_id = None
        if invernadero_seleccionado != "Todos":
            for inv in invernaderos:
                if inv[1] == invernadero_seleccionado:
                    invernadero_id = inv[0]
                    break
    
    stats = get_dashboard_stats(fecha_inicio, fecha_fin, invernadero_id)
    
    # KPIs
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-value">{stats['total_cajas']:,.0f}</div>
            <div class="kpi-label">Cajas Cosechadas</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-value">{stats['total_envios']:,.0f}</div>
            <div class="kpi-label">Cajas Enviadas</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-value">{stats['total_merma']:.1f}</div>
            <div class="kpi-label">Merma (kg)</div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-value">{stats['total_trabajadores']}</div>
            <div class="kpi-label">Trabajadores Activos</div>
        </div>
        """, unsafe_allow_html=True)
    with col5:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-value">{stats['porcentaje_merma']:.1f}%</div>
            <div class="kpi-label">% Merma</div>
        </div>
        """, unsafe_allow_html=True)
    
    # Gráficas
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📈 Evolución de Cosechas")
        cosechas = get_cosechas(fecha_inicio, fecha_fin, invernadero_id)
        if not cosechas.empty:
            df_semanal = cosechas.groupby('semana')['numero_cajas'].sum().reset_index()
            fig = px.line(df_semanal, x='semana', y='numero_cajas', title='Cajas por Semana', markers=True)
            fig.update_traces(line=dict(color='#2ecc71', width=3))
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("🏭 Producción por Invernadero")
        if not cosechas.empty:
            df_inv = cosechas.groupby('invernadero')['numero_cajas'].sum().reset_index().sort_values('numero_cajas', ascending=True)
            fig = px.bar(df_inv, x='numero_cajas', y='invernadero', orientation='h', title='Cajas por Invernadero')
            fig.update_traces(marker_color='#3498db')
            st.plotly_chart(fig, use_container_width=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🗑️ Merma por Tipo")
        merma = get_merma(fecha_inicio, fecha_fin, invernadero_id)
        if not merma.empty:
            df_tipo = merma.groupby('tipo')['kilos'].sum().reset_index()
            fig = px.pie(df_tipo, values='kilos', names='tipo', title='Distribución de Merma')
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("📊 Avance de Cosecha Hoy")
        avance = get_avance_hoy_por_invernadero()
        if not avance.empty:
            fig = px.bar(avance, x='invernadero', y='porcentaje', title='% Avance por Invernadero', text='porcentaje')
            fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
            fig.update_layout(yaxis_title='Porcentaje (%)')
            st.plotly_chart(fig, use_container_width=True)

def mostrar_gestion_usuarios():
    """Panel de administración de usuarios (solo admin)"""
    st.header("👥 Gestión de Usuarios")
    
    if st.session_state.get('user_rol') != 'admin':
        st.error("❌ No tienes permiso para acceder a esta sección")
        return
    
    tab1, tab2, tab3 = st.tabs(["📋 Usuarios", "⚙️ Configuración", "➕ Crear Usuario"])
    
    with tab1:
        usuarios = get_all_users()
        if not usuarios.empty:
            for _, usuario in usuarios.iterrows():
                with st.expander(f"{usuario['nombre']} - {usuario['email']} ({usuario['rol']})"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        nuevo_rol = st.selectbox("Rol", ["admin", "supervisor"], index=0 if usuario['rol'] == 'admin' else 1, key=f"rol_{usuario['id']}")
                        
                        invernaderos = get_all_invernaderos()
                        invernaderos_asignados = st.multiselect(
                            "Invernaderos asignados",
                            [inv[1] for inv in invernaderos],
                            default=[inv for inv in [inv[1] for inv in invernaderos] if inv in usuario.get('invernaderos_asignados', [])],
                            key=f"inv_{usuario['id']}"
                        )
                        
                        invernaderos_ids = [inv[0] for inv in invernaderos if inv[1] in invernaderos_asignados]
                    
                    with col2:
                        st.markdown("**Permisos:**")
                        permisos_actuales = usuario.get('permisos', {})
                        
                        permisos_lista = [
                            ("gestion_personal", "👥 Gestión Personal"),
                            ("registro_cosecha", "🌾 Registro Cosecha"),
                            ("registro_asistencia", "🕐 Control Asistencia"),
                            ("avance_cosecha", "📊 Avance Cosecha"),
                            ("envios_enfriado", "❄️ Envíos a Enfriado"),
                            ("gestion_merma", "🗑️ Gestión Merma"),
                            ("proyecciones", "📈 Proyecciones"),
                            ("generar_qr", "📱 Generar QR"),
                            ("reportes", "📋 Reportes"),
                            ("catalogos", "📚 Catálogos"),
                            ("gestion_invernaderos", "🏭 Gestión Invernaderos"),
                            ("dashboard", "📊 Dashboard"),
                            ("pesaje_cajas", "⚖️ Pesaje Cajas"),
                            ("cajas_mesa", "📦 Cajas en Mesa"),
                            ("cierre_dia", "🔒 Cierre de Día")
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
    
    with tab3:
        st.subheader("Crear Nuevo Usuario")
        
        with st.form("form_nuevo_usuario"):
            email = st.text_input("Email *")
            password = st.text_input("Contraseña *", type="password")
            nombre = st.text_input("Nombre completo *")
            rol = st.selectbox("Rol", ["supervisor", "admin"])
            
            st.markdown("**Permisos (para supervisores):**")
            col1, col2 = st.columns(2)
            with col1:
                perm_gestion_personal = st.checkbox("Gestión Personal")
                perm_registro_cosecha = st.checkbox("Registro Cosecha", value=True)
                perm_registro_asistencia = st.checkbox("Control Asistencia", value=True)
                perm_avance_cosecha = st.checkbox("Avance Cosecha", value=True)
                perm_envios = st.checkbox("Envíos a Enfriado", value=True)
                perm_merma = st.checkbox("Gestión Merma", value=True)
            with col2:
                perm_proyecciones = st.checkbox("Proyecciones", value=True)
                perm_reportes = st.checkbox("Reportes", value=True)
                perm_dashboard = st.checkbox("Dashboard", value=True)
                perm_pesaje = st.checkbox("Pesaje Cajas", value=False)
                perm_cajas_mesa = st.checkbox("Cajas en Mesa", value=False)
                perm_cierre = st.checkbox("Cierre de Día", value=False)
            
            invernaderos = get_all_invernaderos()
            invernaderos_asignados = st.multiselect("Invernaderos asignados", [inv[1] for inv in invernaderos])
            
            if st.form_submit_button("➕ Crear Usuario"):
                if email and password and nombre:
                    permisos = {
                        "gestion_personal": perm_gestion_personal,
                        "registro_cosecha": perm_registro_cosecha,
                        "registro_asistencia": perm_registro_asistencia,
                        "avance_cosecha": perm_avance_cosecha,
                        "envios_enfriado": perm_envios,
                        "gestion_merma": perm_merma,
                        "proyecciones": perm_proyecciones,
                        "generar_qr": False,
                        "reportes": perm_reportes,
                        "catalogos": False,
                        "gestion_invernaderos": False,
                        "dashboard": perm_dashboard,
                        "pesaje_cajas": perm_pesaje,
                        "cajas_mesa": perm_cajas_mesa,
                        "cierre_dia": perm_cierre
                    }
                    
                    invernaderos_ids = [inv[0] for inv in invernaderos if inv[1] in invernaderos_asignados]
                    
                    result = register_user(email, password, nombre, rol, permisos, invernaderos_ids)
                    if result['success']:
                        st.success(result['message'])
                        st.balloons()
                    else:
                        st.error(result['error'])
                else:
                    st.error("Complete los campos obligatorios")

def mostrar_generar_qr():
    st.header("📱 Generar Códigos QR")
    
    if st.session_state.get('user_rol') != 'admin':
        st.error("❌ No tienes permiso para acceder a esta sección")
        return
    
    url_base = st.text_input("URL Base del Sistema", value="https://tu-app.streamlit.app")
    
    trabajadores = get_all_workers()
    
    if not trabajadores.empty:
        opcion = st.radio("Seleccionar", ["Todos", "Seleccionar específicos"])
        
        if opcion == "Todos":
            trabajadores_seleccionados = trabajadores.to_dict('records')
        else:
            nombres = [f"{row['id']} - {row['nombre']} {row['apellido_paterno']}" for _, row in trabajadores.iterrows()]
            seleccionados = st.multiselect("Selecciona trabajadores", nombres)
            trabajadores_seleccionados = [row for _, row in trabajadores.iterrows() if f"{row['id']} - {row['nombre']} {row['apellido_paterno']}" in seleccionados]
        
        if st.button("🔄 Generar QR", use_container_width=True):
            for trabajador in trabajadores_seleccionados:
                nombre_completo = f"{trabajador['nombre']} {trabajador['apellido_paterno']}"
                qr_bytes = generar_qr_trabajador(str(trabajador['id']), nombre_completo, url_base)
                
                col1, col2 = st.columns([1, 2])
                with col1:
                    st.image(qr_bytes, width=150)
                with col2:
                    st.write(f"**{nombre_completo}**")
                    st.write(f"ID: {trabajador['id']}")
                    st.download_button("📥 Descargar QR", data=qr_bytes, file_name=f"QR_{trabajador['id']}_{nombre_completo.replace(' ', '_')}.png", mime="image/png", key=f"qr_{trabajador['id']}")
        
        if st.button("📦 Descargar Todos en ZIP", use_container_width=True):
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for _, trabajador in trabajadores.iterrows():
                    nombre_completo = f"{trabajador['nombre']} {trabajador['apellido_paterno']}"
                    qr_bytes = generar_qr_trabajador(str(trabajador['id']), nombre_completo, url_base)
                    zip_file.writestr(f"QR_{trabajador['id']}_{nombre_completo.replace(' ', '_')}.png", qr_bytes.getvalue())
            zip_buffer.seek(0)
            st.download_button("📥 Descargar ZIP", data=zip_buffer, file_name=f"todos_qr_{datetime.now().strftime('%Y%m%d')}.zip", mime="application/zip")
    else:
        st.warning("Primero agrega trabajadores")

def mostrar_reportes():
    st.header("📋 Reportes")
    
    tab1, tab2 = st.tabs(["📊 Reporte General", "📈 Estadísticas"])
    
    with tab1:
        st.subheader("Generar Reporte por Fechas")
        
        col1, col2 = st.columns(2)
        with col1:
            fecha_reporte_inicio = st.date_input("Fecha inicio", datetime.now().date() - timedelta(days=30))
        with col2:
            fecha_reporte_fin = st.date_input("Fecha fin", datetime.now().date())
        
        if st.button("📊 Generar Reporte"):
            cosechas = get_cosechas(fecha_reporte_inicio, fecha_reporte_fin)
            envios = get_envios_enfriado(fecha_reporte_inicio, fecha_reporte_fin)
            merma = get_merma(fecha_reporte_inicio, fecha_reporte_fin)
            
            st.subheader("📦 Resumen de Cosechas")
            if not cosechas.empty:
                st.dataframe(cosechas, use_container_width=True)
                output1 = export_to_excel(cosechas, "Cosechas")
                st.download_button("📥 Exportar Cosechas", data=output1, file_name=f"cosechas_{datetime.now().date()}.xlsx")
            
            st.subheader("❄️ Resumen de Envíos")
            if not envios.empty:
                st.dataframe(envios, use_container_width=True)
                output2 = export_to_excel(envios, "Envios")
                st.download_button("📥 Exportar Envíos", data=output2, file_name=f"envios_{datetime.now().date()}.xlsx")
            
            st.subheader("🗑️ Resumen de Merma")
            if not merma.empty:
                st.dataframe(merma, use_container_width=True)
                output3 = export_to_excel(merma, "Merma")
                st.download_button("📥 Exportar Merma", data=output3, file_name=f"merma_{datetime.now().date()}.xlsx")
    
    with tab2:
        st.subheader("Estadísticas Avanzadas")
        
        col1, col2 = st.columns(2)
        with col1:
            fecha_est_inicio = st.date_input("Fecha inicio", datetime.now().date() - timedelta(days=90), key="est_inicio")
        with col2:
            fecha_est_fin = st.date_input("Fecha fin", datetime.now().date(), key="est_fin")
        
        cosechas = get_cosechas(fecha_est_inicio, fecha_est_fin)
        
        if not cosechas.empty:
            # Top trabajadores
            top_trabajadores = cosechas.groupby('trabajador')['numero_cajas'].sum().sort_values(ascending=False).head(10)
            fig1 = px.bar(x=top_trabajadores.values, y=top_trabajadores.index, orientation='h', title='Top 10 Trabajadores por Producción')
            st.plotly_chart(fig1, use_container_width=True)
            
            # Producción por tipo
            tipo_prod = cosechas.groupby('tipo_cosecha')['numero_cajas'].sum().reset_index()
            fig2 = px.pie(tipo_prod, values='numero_cajas', names='tipo_cosecha', title='Producción por Tipo')
            st.plotly_chart(fig2, use_container_width=True)
            
            # Tendencia semanal
            semanal = cosechas.groupby('semana')['numero_cajas'].sum().reset_index()
            fig3 = px.line(semanal, x='semana', y='numero_cajas', title='Tendencia Semanal de Producción', markers=True)
            st.plotly_chart(fig3, use_container_width=True)

def mostrar_catalogos():
    st.header("📚 Catálogos")
    
    if st.session_state.get('user_rol') != 'admin':
        st.error("❌ No tienes permiso para acceder a esta sección")
        return
    
    tab1, tab2, tab3 = st.tabs(["🏢 Departamentos", "📂 Subdepartamentos", "💼 Puestos"])
    
    for tab, tabla, get_func in [(tab1, "departamentos", get_departamentos), 
                                   (tab2, "subdepartamentos", get_subdepartamentos), 
                                   (tab3, "puestos", get_puestos)]:
        with tab:
            with st.form(f"new_{tabla}"):
                nuevo = st.text_input(f"Nuevo {tabla[:-1]}")
                if st.form_submit_button("➕ Agregar"):
                    if nuevo:
                        try:
                            supabase.table(tabla).insert({'nombre': nuevo.upper()}).execute()
                            invalidar_cache()
                            st.success(f"✅ {nuevo} agregado")
                            st.rerun()
                        except:
                            st.error("Error al agregar")
            
            items = get_func()
            for id_item, nombre in items:
                col1, col2, col3 = st.columns([4, 1, 1])
                with col1:
                    st.write(f"**{nombre}**")
                with col2:
                    if st.button("✏️", key=f"edit_{tabla}_{id_item}"):
                        nuevo_nombre = st.text_input("Nuevo nombre", value=nombre, key=f"edit_input_{tabla}_{id_item}")
                        if st.button("Guardar", key=f"save_edit_{tabla}_{id_item}"):
                            try:
                                supabase.table(tabla).update({'nombre': nuevo_nombre.upper()}).eq('id', id_item).execute()
                                invalidar_cache()
                                st.rerun()
                            except:
                                st.error("Error")
                with col3:
                    if st.button("🗑️", key=f"del_{tabla}_{id_item}"):
                        try:
                            supabase.table(tabla).delete().eq('id', id_item).execute()
                            invalidar_cache()
                            st.rerun()
                        except:
                            st.error("Error al eliminar")
                st.markdown("---")

def mostrar_gestion_invernaderos():
    st.header("🏭 Gestión de Invernaderos")
    
    if st.session_state.get('user_rol') != 'admin':
        st.error("❌ No tienes permiso para acceder a esta sección")
        return
    
    with st.form("form_invernadero"):
        col1, col2, col3 = st.columns(3)
        with col1:
            nombre = st.text_input("Nombre del Invernadero *")
        with col2:
            ubicacion = st.text_input("Ubicación *")
        with col3:
            lineas_totales = st.number_input("Líneas totales", min_value=1, max_value=100, value=40)
        
        if st.form_submit_button("➕ Agregar Invernadero"):
            if nombre and ubicacion:
                try:
                    supabase.table('invernaderos').insert({
                        'nombre': nombre.upper(),
                        'ubicacion': ubicacion,
                        'lineas_totales': lineas_totales
                    }).execute()
                    invalidar_cache()
                    st.success("✅ Invernadero agregado")
                    st.rerun()
                except:
                    st.error("Error al agregar")
            else:
                st.error("Complete los campos")
    
    st.markdown("---")
    st.subheader("Lista de Invernaderos")
    
    invernaderos = get_all_invernaderos()
    for id_inv, nombre, ubicacion, lineas in invernaderos:
        with st.container():
            col1, col2, col3, col4, col5 = st.columns([3, 2, 1, 1, 1])
            with col1:
                st.write(f"**{nombre}**")
            with col2:
                st.write(f"📍 {ubicacion}")
            with col3:
                st.write(f"📏 {lineas} líneas")
            with col4:
                if st.button("✏️", key=f"edit_inv_{id_inv}"):
                    st.session_state[f'editing_inv_{id_inv}'] = True
            with col5:
                if st.button("🗑️", key=f"del_inv_{id_inv}"):
                    try:
                        supabase.table('invernaderos').update({'activo': False}).eq('id', id_inv).execute()
                        invalidar_cache()
                        st.rerun()
                    except:
                        st.error("Error")
            
            if st.session_state.get(f'editing_inv_{id_inv}', False):
                with st.form(key=f"form_edit_inv_{id_inv}"):
                    nuevo_nombre = st.text_input("Nombre", value=nombre)
                    nueva_ubicacion = st.text_input("Ubicación", value=ubicacion)
                    nuevas_lineas = st.number_input("Líneas totales", value=lineas)
                    
                    col_yes, col_no = st.columns(2)
                    with col_yes:
                        if st.form_submit_button("💾 Guardar"):
                            try:
                                supabase.table('invernaderos').update({
                                    'nombre': nuevo_nombre.upper(),
                                    'ubicacion': nueva_ubicacion,
                                    'lineas_totales': nuevas_lineas
                                }).eq('id', id_inv).execute()
                                invalidar_cache()
                                del st.session_state[f'editing_inv_{id_inv}']
                                st.rerun()
                            except:
                                st.error("Error")
                    with col_no:
                        if st.form_submit_button("❌ Cancelar"):
                            del st.session_state[f'editing_inv_{id_inv}']
                            st.rerun()
            st.markdown("---")

def mostrar_menu_sidebar():
    """Muestra el menú lateral según los permisos del usuario"""
    
    st.sidebar.markdown("""
    <div class="sidebar-title">
        <h2>🌾 Sistema Integral</h2>
        <p>Gestión Agrícola</p>
    </div>
    """, unsafe_allow_html=True)
    
    if st.session_state.get('authenticated', False):
        st.sidebar.markdown(f"""
        <div class="user-info">
            👤 <strong>{st.session_state.get('user_nombre', 'Usuario')}</strong><br>
            📧 {st.session_state.get('user_email', '')}<br>
            🎭 Rol: <strong>{st.session_state.get('user_rol', 'supervisor').upper()}</strong>
        </div>
        """, unsafe_allow_html=True)
    
    permisos, rol, _ = obtener_permisos_usuario(st.session_state.get('user_id'))
    
    # Menú completo para admin
    if rol == 'admin':
        menu_options = {
            "📊 Dashboard": "Estadísticas generales",
            "🌾 Registro Cosecha": "Registrar producción",
            "👥 Gestión Personal": "Alta/baja/editar trabajadores",
            "🕐 Control Asistencia": "Registro entrada/salida",
            "📊 Avance Cosecha": "Registrar avance por invernadero",
            "❄️ Envíos a Enfriado": "Cajas a enfriado y pesaje",
            "📦 Cajas en Mesa": "Registro de cajas en mesa",
            "🗑️ Gestión Merma": "Registro de merma",
            "📈 Proyecciones": "Comparativa real vs proyectado",
            "🔒 Cierre de Día": "Cierre y reportes diarios",
            "📱 Generar QR": "Códigos QR para trabajadores",
            "📋 Reportes": "Reportes y estadísticas",
            "📚 Catálogos": "Departamentos, puestos, etc.",
            "🏭 Gestión Invernaderos": "Administrar invernaderos",
            "👥 Gestión Usuarios": "Administrar usuarios y permisos"
        }
    else:
        # Menú para supervisores según permisos
        menu_options = {}
        if permisos.get('dashboard', True):
            menu_options["📊 Dashboard"] = "Estadísticas generales"
        if permisos.get('registro_cosecha', True):
            menu_options["🌾 Registro Cosecha"] = "Registrar producción"
        if permisos.get('registro_asistencia', True):
            menu_options["🕐 Control Asistencia"] = "Registro entrada/salida"
        if permisos.get('avance_cosecha', True):
            menu_options["📊 Avance Cosecha"] = "Registrar avance por invernadero"
        if permisos.get('envios_enfriado', True):
            menu_options["❄️ Envíos a Enfriado"] = "Cajas a enfriado y pesaje"
        if permisos.get('cajas_mesa', False):
            menu_options["📦 Cajas en Mesa"] = "Registro de cajas en mesa"
        if permisos.get('gestion_merma', True):
            menu_options["🗑️ Gestión Merma"] = "Registro de merma"
        if permisos.get('proyecciones', True):
            menu_options["📈 Proyecciones"] = "Comparativa real vs proyectado"
        if permisos.get('cierre_dia', False):
            menu_options["🔒 Cierre de Día"] = "Cierre y reportes diarios"
        if permisos.get('reportes', True):
            menu_options["📋 Reportes"] = "Reportes y estadísticas"
    
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
        st.error("❌ No se pudo conectar a Supabase")
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
        mostrar_dashboard()
    elif st.session_state.menu == "🌾 Registro Cosecha":
        mostrar_registro_cosecha()
    elif st.session_state.menu == "👥 Gestión Personal":
        mostrar_gestion_personal()
    elif st.session_state.menu == "🕐 Control Asistencia":
        mostrar_control_asistencia()
    elif st.session_state.menu == "📊 Avance Cosecha":
        mostrar_avance_cosecha()
    elif st.session_state.menu == "❄️ Envíos a Enfriado":
        mostrar_envios_enfriado()
    elif st.session_state.menu == "📦 Cajas en Mesa":
        mostrar_cajas_mesa()
    elif st.session_state.menu == "🗑️ Gestión Merma":
        mostrar_gestion_merma()
    elif st.session_state.menu == "📈 Proyecciones":
        mostrar_proyecciones()
    elif st.session_state.menu == "🔒 Cierre de Día":
        mostrar_cierre_dia()
    elif st.session_state.menu == "📱 Generar QR":
        mostrar_generar_qr()
    elif st.session_state.menu == "📋 Reportes":
        mostrar_reportes()
    elif st.session_state.menu == "📚 Catálogos":
        mostrar_catalogos()
    elif st.session_state.menu == "🏭 Gestión Invernaderos":
        mostrar_gestion_invernaderos()
    elif st.session_state.menu == "👥 Gestión Usuarios":
        mostrar_gestion_usuarios()

if __name__ == "__main__":
    main()
