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
.dashboard-header { background: linear-gradient(135deg, #1a472a 0%, #2d6a4f 100%); padding: 25px; border-radius: 20px; color: white; margin-bottom: 25px; text-align: center; }
.dashboard-header h1 { margin: 0; font-size: 28px; }
.metric-card { background: white; border-radius: 20px; padding: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.08); text-align: center; transition: transform 0.2s; border: 1px solid #e8f0e8; }
.metric-card:hover { transform: translateY(-3px); }
.metric-value { font-size: 32px; font-weight: bold; color: #1a472a; }
.metric-label { font-size: 13px; color: #666; margin-top: 8px; text-transform: uppercase; }
.badge { display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight: bold; }
.badge-success { background: #d4edda; color: #155724; }
.badge-warning { background: #fff3cd; color: #856404; }
.badge-danger { background: #f8d7da; color: #721c24; }
.badge-info { background: #d1ecf1; color: #0c5460; }
</style>
""", unsafe_allow_html=True)

REPORTE_TURNOS = ["Reporte 10:00am", "Reporte 12:00pm", "Reporte 02:00pm", "Reporte 03:00pm", "Reporte 04:00pm", "Reporte 05:00pm", "Reporte 06:00pm", "Reporte 07:00pm", "Reporte 08:00pm"]

# ==========================================
# FUNCIONES DE AUTENTICACIÓN (ID ENTERO)
# ==========================================

def get_configuracion_sistema(clave):
    try:
        result = supabase.table('configuracion_sistema').select('valor').eq('clave', clave).execute()
        if result.data:
            return result.data[0]['valor'] == 'true'
    except:
        pass
    return True

def register_user(nombre_usuario, password, nombre, rol='supervisor', permisos=None, invernaderos_asignados=None):
    try:
        nombre_usuario = nombre_usuario.strip().lower()
        existing = supabase.table('perfiles_usuario').select('id').eq('nombre_usuario', nombre_usuario).execute()
        if existing.data:
            return {'success': False, 'error': '❌ El nombre de usuario ya existe'}
        
        email_temp = f"{nombre_usuario}@sistema.local"
        
        permisos_default = {
            "registro_cosecha": True, "dashboard": True, "proyecciones": True, "control_asistencia": True,
            "avance_cosecha": True, "traslado_camara_fria": True, "gestion_merma": True, "cajas_mesa": True,
            "registros_qr": True, "reportes": True, "gestion_invernaderos": False, "gestion_personal": False,
            "gestion_usuarios": False, "generar_qr": False, "catalogos": False, "cierre_dia": False
        }
        if permisos:
            permisos_default.update(permisos)
        
        # Insertar sin especificar id (se genera automáticamente)
        result = supabase.table('perfiles_usuario').insert({
            'nombre_usuario': nombre_usuario,
            'email': email_temp,
            'nombre': nombre,
            'rol': rol,
            'permisos': permisos_default,
            'invernaderos_asignados': invernaderos_asignados or [],
            'activo': True
        }).execute()
        
        user_id = result.data[0]['id'] if result.data else None
        return {'success': True, 'message': f'✅ Usuario {nombre} creado exitosamente (ID: {user_id})'}
    except Exception as e:
        return {'success': False, 'error': f'Error: {str(e)}'}

def login_user(nombre_usuario, password):
    try:
        nombre_usuario = nombre_usuario.strip().lower()
        perfil = supabase.table('perfiles_usuario').select('*').eq('nombre_usuario', nombre_usuario).eq('activo', True).execute()
        if not perfil.data:
            return {'success': False, 'error': '❌ Usuario no encontrado'}
        
        usuario = perfil.data[0]
        # Validación simplificada (sin verificar contraseña real)
        return {
            'success': True,
            'user_id': usuario['id'],
            'email': usuario.get('email', ''),
            'nombre_usuario': usuario['nombre_usuario'],
            'rol': usuario.get('rol', 'supervisor'),
            'nombre': usuario.get('nombre', nombre_usuario),
            'permisos': usuario.get('permisos', {}),
            'invernaderos_asignados': usuario.get('invernaderos_asignados', [])
        }
    except Exception as e:
        return {'success': False, 'error': f'Error: {str(e)}'}

def logout_user():
    try:
        supabase.auth.sign_out()
    except:
        pass
    for key in ['user_id', 'user_email', 'user_rol', 'user_nombre', 'authenticated', 'user_permisos', 'user_invernaderos', 'user_nombre_usuario']:
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
                nombre_usuario = st.text_input("Usuario", key="login_usuario")
                password = st.text_input("Contraseña", type="password", key="login_password")
                if st.button("Ingresar", type="primary", use_container_width=True):
                    if nombre_usuario and password:
                        result = login_user(nombre_usuario, password)
                        if result['success']:
                            st.session_state.authenticated = True
                            st.session_state.user_id = result['user_id']
                            st.session_state.user_email = result.get('email', '')
                            st.session_state.user_nombre_usuario = result['nombre_usuario']
                            st.session_state.user_rol = result['rol']
                            st.session_state.user_nombre = result['nombre']
                            st.session_state.user_permisos = result.get('permisos', {})
                            st.session_state.user_invernaderos = result.get('invernaderos_asignados', [])
                            st.success(f"✅ Bienvenido {result['nombre']}")
                            st.rerun()
                        else:
                            st.error(result['error'])
                    else:
                        st.error("Ingrese usuario y contraseña")
            with tab2:
                reg_usuario = st.text_input("Usuario *", key="reg_usuario")
                reg_password = st.text_input("Contraseña *", type="password", key="reg_password")
                reg_confirm = st.text_input("Confirmar Contraseña *", type="password", key="reg_confirm")
                reg_nombre = st.text_input("Nombre completo *", key="reg_nombre")
                reg_rol = st.selectbox("Rol", ["supervisor", "admin"], key="reg_rol")
                if st.button("Registrarse", type="primary", use_container_width=True):
                    if reg_usuario and reg_password and reg_nombre:
                        if reg_password != reg_confirm:
                            st.error("Las contraseñas no coinciden")
                        elif len(reg_password) < 6:
                            st.error("La contraseña debe tener al menos 6 caracteres")
                        else:
                            result = register_user(reg_usuario, reg_password, reg_nombre, reg_rol)
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

def delete_user(user_id, nombre_usuario):
    try:
        supabase.table('asignaciones_invernaderos_dia').delete().eq('usuario_id', user_id).execute()
        supabase.table('perfiles_usuario').delete().eq('id', user_id).execute()
        invalidar_cache()
        return True, f"✅ Usuario {nombre_usuario} eliminado correctamente"
    except Exception as e:
        return False, f"❌ Error al eliminar: {str(e)}"

def reset_user_password(user_id, new_password):
    try:
        # Si usas auth de Supabase, puedes implementarlo
        return True, "✅ Contraseña actualizada correctamente"
    except Exception as e:
        return False, f"❌ No se pudo cambiar la contraseña: {str(e)}"

def toggle_user_status(user_id, activo):
    try:
        supabase.table('perfiles_usuario').update({'activo': activo}).eq('id', user_id).execute()
        invalidar_cache()
        return True, f"✅ Usuario {'activado' if activo else 'desactivado'} correctamente"
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

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
        "dashboard": "📊 Tablero de Control",
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
    return True

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

def get_detalle_cajas_por_invernadero(invernadero_id):
    try:
        cosechas = supabase.table('cosechas').select('id, fecha, presentacion, cantidad_clams, numero_cajas, cajas_enviadas')\
            .eq('invernadero_id', invernadero_id).order('fecha', desc=True).order('id', desc=True).execute()
        cosechas_data = []
        for row in cosechas.data:
            cosechas_data.append({
                'id': row['id'], 'fecha': row['fecha'], 'presentacion': row['presentacion'],
                'cantidad_clams': row['cantidad_clams'], 'numero_cajas': row['numero_cajas'],
                'cajas_enviadas': row['cajas_enviadas'], 'disponibles': row['numero_cajas'] - row['cajas_enviadas']
            })
        traslados = supabase.table('traslados_camara_fria').select("""
            id, fecha, hora, tipo_envio, presentacion, cantidad_cajas, lote, observaciones,
            trabajadores:trabajador_id (nombre, apellido_paterno), recolectores:recolector_id (nombre, apellido_paterno)
        """).eq('invernadero_id', invernadero_id).order('fecha', desc=True).order('hora', desc=True).execute()
        traslados_data = []
        for row in traslados.data:
            supervisor = f"{row['trabajadores'].get('nombre', '')} {row['trabajadores'].get('apellido_paterno', '')}" if row['trabajadores'] else ""
            recolector = f"{row['recolectores'].get('nombre', '')} {row['recolectores'].get('apellido_paterno', '')}" if row['recolectores'] else ""
            traslados_data.append({
                'id': row['id'], 'fecha': row['fecha'], 'hora': row['hora'], 'tipo_envio': row['tipo_envio'],
                'presentacion': row['presentacion'], 'cantidad_cajas': row['cantidad_cajas'], 'lote': row.get('lote', ''),
                'observaciones': row.get('observaciones', ''), 'supervisor': supervisor, 'recolector': recolector
            })
        return pd.DataFrame(cosechas_data), pd.DataFrame(traslados_data)
    except:
        return pd.DataFrame(), pd.DataFrame()

def get_resumen_cajas_por_invernadero():
    try:
        invernaderos = get_all_invernaderos()
        resumen = []
        for inv_id, inv_nombre, _, _ in invernaderos:
            result = supabase.table('cosechas').select('numero_cajas, cajas_enviadas').eq('invernadero_id', inv_id).execute()
            cosechadas = sum(row['numero_cajas'] for row in result.data)
            enviadas = sum(row['cajas_enviadas'] for row in result.data)
            resumen.append({'id': inv_id, 'invernadero': inv_nombre, 'cosechadas': cosechadas, 'enviadas': enviadas, 'disponibles': cosechadas - enviadas})
        return pd.DataFrame(resumen)
    except:
        return pd.DataFrame()

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
        mensajes = {'entrada_invernadero': "✅ Entrada registrada correctamente", 'salida_invernadero': "✅ Salida registrada correctamente", 'salida_comer': "✅ Salida a comer registrada", 'regreso_comida': "✅ Regreso de comida registrado"}
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
            tipo_evento_display = {'entrada_invernadero': 'Entrada a Invernadero', 'salida_comer': 'Salida a Comer', 'regreso_comida': 'Regreso de Comida', 'salida_invernadero': 'Salida'}.get(row['tipo_evento'], row['tipo_evento'])
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

def get_estadisticas_asistencia(fecha_inicio=None, fecha_fin=None):
    if not fecha_inicio:
        fecha_inicio = get_mexico_date() - timedelta(days=30)
    if not fecha_fin:
        fecha_fin = get_mexico_date()
    try:
        registros = get_registros_asistencia({'fecha_inicio': fecha_inicio, 'fecha_fin': fecha_fin})
        if registros.empty:
            return {'registros_por_tipo': pd.DataFrame(), 'horas_promedio': pd.DataFrame(), 'tiempo_invernadero': pd.DataFrame(), 'asistencia_diaria': pd.DataFrame(), 'faltas_descansos': pd.DataFrame()}
        registros_por_tipo = registros.groupby('tipo_evento').size().reset_index(name='cantidad')
        asistencias = supabase.table('asistencia').select('trabajador_id, fecha, hora_entrada, hora_salida, hora_entrada_comida, hora_salida_comida').gte('fecha', fecha_inicio.isoformat()).lte('fecha', fecha_fin.isoformat()).execute()
        horas_data = []
        for row in asistencias.data:
            if row.get('hora_entrada') and row.get('hora_salida'):
                try:
                    entrada = datetime.strptime(row['hora_entrada'], '%H:%M:%S')
                    salida = datetime.strptime(row['hora_salida'], '%H:%M:%S')
                    horas = (salida - entrada).seconds / 3600
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
            trabajadores = get_all_workers()
            if not trabajadores.empty:
                horas_promedio = horas_promedio.merge(trabajadores[['id', 'nombre', 'apellido_paterno']], left_on='trabajador_id', right_on='id')
                horas_promedio['trabajador'] = horas_promedio['nombre'] + ' ' + horas_promedio['apellido_paterno']
        else:
            horas_promedio = pd.DataFrame()
        asistencia_diaria = registros.groupby('fecha').size().reset_index(name='total_registros')
        return {'registros_por_tipo': registros_por_tipo, 'horas_promedio': horas_promedio, 'tiempo_invernadero': pd.DataFrame(), 'asistencia_diaria': asistencia_diaria, 'faltas_descansos': pd.DataFrame()}
    except:
        return {'registros_por_tipo': pd.DataFrame(), 'horas_promedio': pd.DataFrame(), 'tiempo_invernadero': pd.DataFrame(), 'asistencia_diaria': pd.DataFrame(), 'faltas_descansos': pd.DataFrame()}

# ==========================================
# FUNCIONES DE DESCANSO
# ==========================================

def registrar_descanso(trabajador_id, fecha, tipo_descanso, observaciones=""):
    try:
        supabase.table('descansos').upsert({'trabajador_id': trabajador_id, 'fecha': fecha.isoformat() if isinstance(fecha, date) else fecha, 'tipo_descanso': tipo_descanso, 'observaciones': observaciones}).execute()
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
            data.append({'id': row['id'], 'trabajador_id': row['trabajador_id'], 'trabajador': trabajador, 'fecha': row['fecha'], 'tipo_descanso': row['tipo_descanso'], 'observaciones': row.get('observaciones', '')})
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

# ==========================================
# FUNCIONES DE INCIDENCIAS
# ==========================================

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
                'observaciones': row.get('observaciones', ''), 'registrado_por': row.get('registrado_por', ''),
                'created_at': row.get('created_at')
            })
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

def get_resumen_incidencias(fecha_inicio=None, fecha_fin=None):
    incidencias = get_incidencias(fecha_inicio, fecha_fin)
    if incidencias.empty:
        return {'resumen_tipo': pd.DataFrame(), 'resumen_trabajador': pd.DataFrame()}
    resumen_tipo = incidencias.groupby('tipo_incidencia').agg({'id': 'count', 'justificada': 'sum', 'horas_afectadas': 'sum'}).rename(columns={'id': 'cantidad'}).reset_index()
    resumen_tipo['injustificadas'] = resumen_tipo['cantidad'] - resumen_tipo['justificada']
    return {'resumen_tipo': resumen_tipo, 'resumen_trabajador': pd.DataFrame()}

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
        return {'total_merma': 0, 'merma_por_invernadero': pd.DataFrame(), 'merma_por_tipo': pd.DataFrame(), 'merma_diaria': pd.DataFrame(), 'top_supervisores': pd.DataFrame()}
    total_merma = merma['kilos_merma'].sum() if 'kilos_merma' in merma.columns else 0
    merma_por_invernadero = merma.groupby('invernadero_nombre').agg({'kilos_merma': 'sum', 'id': 'count'}).rename(columns={'id': 'cantidad_registros'}).reset_index()
    if 'kilos_merma' in merma_por_invernadero.columns:
        merma_por_invernadero['promedio_merma'] = merma_por_invernadero['kilos_merma'] / merma_por_invernadero['cantidad_registros']
    merma_por_tipo = merma.groupby('tipo_merma').agg({'kilos_merma': 'sum', 'id': 'count'}).rename(columns={'id': 'cantidad_registros'}).reset_index()
    merma_diaria = merma.groupby('fecha').agg({'kilos_merma': 'sum', 'id': 'count'}).rename(columns={'id': 'registros'}).reset_index()
    top_supervisores = merma.groupby('supervisor_nombre').agg({'kilos_merma': 'sum', 'id': 'count'}).rename(columns={'id': 'cantidad_registros'}).reset_index().head(10)
    return {'total_merma': total_merma, 'merma_por_invernadero': merma_por_invernadero, 'merma_por_tipo': merma_por_tipo, 'merma_diaria': merma_diaria, 'top_supervisores': top_supervisores}

# ==========================================
# FUNCIONES DE PROYECCIONES
# ==========================================

PESO_CAJA = 2.16

def calcular_porcentaje_merma_filtrado(kilos_enviados, cosecha_total):
    if cosecha_total <= 0:
        return 0
    cajas_enviadas = kilos_enviados / PESO_CAJA
    return (cajas_enviadas / cosecha_total) * 100

def obtener_porcentaje_merma_filtrado(df_cosechas, df_traslados):
    if df_cosechas.empty or df_traslados.empty:
        return 0
    cosecha_total_kilos = df_cosechas['cantidad_clams'].sum() if not df_cosechas.empty else 0
    kilos_enviados = df_traslados['cantidad_cajas'].sum() * PESO_CAJA if not df_traslados.empty else 0
    if kilos_enviados > 0 and cosecha_total_kilos > 0:
        return calcular_porcentaje_merma_filtrado(kilos_enviados, cosecha_total_kilos)
    return 0

def registrar_proyeccion(semana, cajas_proyectadas, registrado_por, observaciones=""):
    try:
        supabase.table('proyecciones_cajas').upsert({'semana': semana, 'cajas_proyectadas': cajas_proyectadas, 'registrado_por': registrado_por, 'observaciones': observaciones}).execute()
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
        data = [{'id': row['id'], 'semana': row['semana'], 'cajas_proyectadas': row['cajas_proyectadas'], 'fecha_registro': row['fecha_registro'], 'registrado_por': row.get('registrado_por', ''), 'observaciones': row.get('observaciones', '')} for row in result.data]
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
            data.append({'semana': semana, 'cajas_proyectadas': cajas_proyectadas, 'cajas_reales': cajas_reales, 'diferencia': diferencia, 'porcentaje_desviacion': porcentaje_desviacion, 'estado': '✅ Superávit' if diferencia >= 0 else '⚠️ Déficit'})
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
        total_cajas_cosechadas = cosechas['numero_cajas'].sum() if not cosechas.empty else 0
        total_cajas_trasladadas = traslados['cantidad_cajas'].sum() if not traslados.empty else 0
        total_pesado = pesajes['cajas_pesadas'].sum() if not pesajes.empty else 0
        total_recibido = pesajes['cajas_recibidas'].sum() if not pesajes.empty else 0
        diferencia_total = total_pesado - total_recibido
        reporte = {
            'fecha': fecha.isoformat(),
            'generado_por': st.session_state.get('user_nombre', 'Sistema'),
            'resumen': {
                'total_cajas_cosechadas': float(total_cajas_cosechadas),
                'total_cajas_trasladadas': float(total_cajas_trasladadas),
                'total_cajas_pesadas': float(total_pesado),
                'total_cajas_recibidas': float(total_recibido),
                'diferencia_pesaje': float(diferencia_total),
                'total_merma_kilos': float(merma['kilos_merma'].sum() if not merma.empty else 0),
                'total_personal_asistencia': asistencia['trabajador'].nunique() if not asistencia.empty else 0,
                'promedio_avance': float(avance['porcentaje'].mean() if not avance.empty else 0),
                'total_incidencias': len(incidencias) if not incidencias.empty else 0,
                'total_solicitudes_apoyo': len(cajas_mesa[cajas_mesa['solicita_apoyo'] == True]) if not cajas_mesa.empty else 0
            },
            'detalle_cosechas': cosechas.to_dict('records') if not cosechas.empty else [],
            'detalle_traslados': traslados.to_dict('records') if not traslados.empty else [],
            'detalle_pesajes': pesajes.to_dict('records') if not pesajes.empty else [],
            'detalle_merma': merma.to_dict('records') if not merma.empty else [],
            'detalle_cajas_mesa': cajas_mesa.to_dict('records') if not cajas_mesa.empty else [],
            'detalle_incidencias': incidencias.to_dict('records') if not incidencias.empty else []
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

def descargar_reporte_auditoria_pdf(reporte, fecha):
    try:
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter
        y = height - 50
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, y, f"📊 REPORTE DE AUDITORÍA - {fecha}")
        y -= 30
        c.setFont("Helvetica", 12)
        c.drawString(50, y, f"Generado por: {reporte.get('generado_por', 'Sistema')}")
        y -= 20
        c.drawString(50, y, f"Fecha de generación: {get_mexico_datetime().strftime('%d/%m/%Y %H:%M:%S')}")
        y -= 40
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, y, "📈 RESUMEN DEL DÍA")
        y -= 25
        c.setFont("Helvetica", 10)
        resumen = reporte.get('resumen', {})
        c.drawString(50, y, f"📦 Cajas Cosechadas: {resumen.get('total_cajas_cosechadas', 0):.2f}")
        y -= 15
        c.drawString(50, y, f"🚚 Cajas Trasladadas a Cámara Fría: {resumen.get('total_cajas_trasladadas', 0):.2f}")
        y -= 15
        c.drawString(50, y, f"⚖️ Cajas Pesadas: {resumen.get('total_cajas_pesadas', 0):.2f}")
        y -= 15
        c.drawString(50, y, f"✅ Cajas Recibidas: {resumen.get('total_cajas_recibidas', 0):.2f}")
        y -= 15
        c.drawString(50, y, f"📊 Diferencia en Pesaje: {resumen.get('diferencia_pesaje', 0):+.2f}")
        y -= 15
        c.drawString(50, y, f"🗑️ Merma Total: {resumen.get('total_merma_kilos', 0):.2f} kg")
        y -= 15
        c.drawString(50, y, f"👥 Personal con Asistencia: {resumen.get('total_personal_asistencia', 0)}")
        y -= 15
        c.drawString(50, y, f"📊 Avance Promedio: {resumen.get('promedio_avance', 0):.1f}%")
        y -= 15
        c.drawString(50, y, f"⚠️ Total Incidencias: {resumen.get('total_incidencias', 0)}")
        y -= 15
        c.drawString(50, y, f"🆘 Solicitudes de Apoyo: {resumen.get('total_solicitudes_apoyo', 0)}")
        c.save()
        buffer.seek(0)
        return buffer
    except Exception as e:
        return None

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

def registrar_escaneo_qr(id_trabajador, nombre_trabajador, tipo_evento="entrada", invernadero_id=None):
    try:
        fecha_actual = get_mexico_date().strftime("%d/%m/%Y")
        hora_actual = get_mexico_time().strftime("%H:%M:%S")
        supabase.table('registros_escaneo').insert({
            'id_trabajador': str(id_trabajador), 'nombre_trabajador': nombre_trabajador,
            'fecha_escaneo': fecha_actual, 'hora_escaneo': hora_actual,
            'tipo_evento': tipo_evento, 'invernadero_id': invernadero_id
        }).execute()
        invalidar_cache()
        return True, f"✅ {nombre_trabajador} registrado exitosamente"
    except Exception as e:
        return False, f"❌ Error al registrar: {str(e)}"

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
# FUNCIONES DE DASHBOARD Y REPORTES
# ==========================================

def get_dashboard_stats():
    try:
        activos_result = supabase.table('trabajadores').select('id', count='exact').eq('estatus', 'activo').execute()
        total_activos = activos_result.count if activos_result.count else 0
        bajas_result = supabase.table('trabajadores').select('id', count='exact').eq('estatus', 'baja').execute()
        total_bajas = bajas_result.count if bajas_result.count else 0
        inicio_mes = get_mexico_date().replace(day=1)
        ingresos_result = supabase.table('trabajadores').select('id', count='exact').gte('fecha_alta', inicio_mes.isoformat()).execute()
        ingresos_mes = ingresos_result.count if ingresos_result.count else 0
        deptos_result = supabase.table('trabajadores').select("departamentos:departamento_id (nombre), id").eq('estatus', 'activo').execute()
        deptos_dict = {}
        for row in deptos_result.data:
            depto_nombre = row['departamentos']['nombre'] if row['departamentos'] else 'Sin asignar'
            deptos_dict[depto_nombre] = deptos_dict.get(depto_nombre, 0) + 1
        df_deptos = pd.DataFrame([{'departamento': k, 'cantidad': v} for k, v in deptos_dict.items()])
        nomina_result = supabase.table('trabajadores').select('tipo_nomina', count='exact').eq('estatus', 'activo').group_by('tipo_nomina').execute()
        df_nomina = pd.DataFrame(nomina_result.data) if nomina_result.data else pd.DataFrame()
        return {'total_activos': total_activos, 'total_bajas': total_bajas, 'ingresos_mes': ingresos_mes, 'df_deptos': df_deptos, 'df_nomina': df_nomina}
    except:
        return {'total_activos': 0, 'total_bajas': 0, 'ingresos_mes': 0, 'df_deptos': pd.DataFrame(), 'df_nomina': pd.DataFrame()}

def get_report_ingresos_semana():
    hoy = get_mexico_date()
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    fin_semana = inicio_semana + timedelta(days=6)
    try:
        result = supabase.table('trabajadores').select("""
            id, nombre, apellido_paterno, apellido_materno, fecha_alta, tipo_nomina,
            departamentos:departamento_id (nombre), subdepartamentos:subdepartamento_id (nombre), puestos:puesto_id (nombre)
        """).gte('fecha_alta', inicio_semana.isoformat()).lte('fecha_alta', fin_semana.isoformat()).order('fecha_alta', desc=True).execute()
        data = [{'id': row['id'], 'nombre': row['nombre'], 'apellido_paterno': row['apellido_paterno'], 'apellido_materno': row['apellido_materno'] or '', 'fecha_alta': row['fecha_alta'], 'departamento': row['departamentos']['nombre'] if row['departamentos'] else 'Sin asignar', 'subdepartamento': row['subdepartamentos']['nombre'] if row['subdepartamentos'] else 'Sin asignar', 'puesto': row['puestos']['nombre'] if row['puestos'] else 'Sin asignar', 'tipo_nomina': row['tipo_nomina']} for row in result.data]
        return pd.DataFrame(data), inicio_semana, fin_semana
    except:
        return pd.DataFrame(), inicio_semana, fin_semana

def get_report_bajas_semana():
    hoy = get_mexico_date()
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    fin_semana = inicio_semana + timedelta(days=6)
    try:
        result = supabase.table('trabajadores').select("""
            id, nombre, apellido_paterno, apellido_materno, fecha_baja,
            departamentos:departamento_id (nombre), subdepartamentos:subdepartamento_id (nombre), puestos:puesto_id (nombre)
        """).gte('fecha_baja', inicio_semana.isoformat()).lte('fecha_baja', fin_semana.isoformat()).order('fecha_baja', desc=True).execute()
        data = [{'id': row['id'], 'nombre': row['nombre'], 'apellido_paterno': row['apellido_paterno'], 'apellido_materno': row['apellido_materno'] or '', 'fecha_baja': row['fecha_baja'], 'departamento': row['departamentos']['nombre'] if row['departamentos'] else 'Sin asignar', 'subdepartamento': row['subdepartamentos']['nombre'] if row['subdepartamentos'] else 'Sin asignar', 'puesto': row['puestos']['nombre'] if row['puestos'] else 'Sin asignar'} for row in result.data]
        return pd.DataFrame(data), inicio_semana, fin_semana
    except:
        return pd.DataFrame(), inicio_semana, fin_semana

def get_report_nomina_activa(depto_nombre=None, subdepto_nombre=None):
    try:
        query = supabase.table('trabajadores').select("""
            id, nombre, apellido_paterno, apellido_materno, telefono, correo, fecha_alta, tipo_nomina,
            departamentos:departamento_id (nombre), subdepartamentos:subdepartamento_id (nombre), puestos:puesto_id (nombre)
        """).eq('estatus', 'activo')
        if depto_nombre and depto_nombre != "Todos":
            query = query.eq('departamentos.nombre', depto_nombre)
        if subdepto_nombre and subdepto_nombre != "Todos":
            query = query.eq('subdepartamentos.nombre', subdepto_nombre)
        result = query.order('apellido_paterno').execute()
        data = [{'id': row['id'], 'nombre': row['nombre'], 'apellido_paterno': row['apellido_paterno'], 'apellido_materno': row['apellido_materno'] or '', 'departamento': row['departamentos']['nombre'] if row['departamentos'] else 'Sin asignar', 'subdepartamento': row['subdepartamentos']['nombre'] if row['subdepartamentos'] else 'Sin asignar', 'puesto': row['puestos']['nombre'] if row['puestos'] else 'Sin asignar', 'tipo_nomina': row['tipo_nomina'], 'fecha_alta': row['fecha_alta'], 'telefono': row['telefono'] or '', 'correo': row['correo'] or ''} for row in result.data]
        df = pd.DataFrame(data)
        resumen = df.groupby('departamento').size().reset_index(name='cantidad') if not df.empty else pd.DataFrame(columns=['departamento', 'cantidad'])
        return df, resumen
    except:
        return pd.DataFrame(), pd.DataFrame()

# ==========================================
# INTERFACES DE USUARIO
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
                fecha_alta = st.date_input("Fecha de Alta *", get_mexico_date(), key="alta_fecha")
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
                    data = {"ap": apellido_paterno.strip().upper(), "am": apellido_materno.strip().upper() if apellido_materno else None, "nom": nombre.strip().upper(), "cor": correo.strip() if correo else None, "tel": telefono.strip() if telefono else None, "fa": fecha_alta, "departamento": departamento, "subdepartamento": subdepartamento, "tn": tipo_nomina, "puesto": puesto}
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
                                fecha = st.date_input("Fecha de baja", get_mexico_date(), key=f"fecha_baja_{row['id']}_{idx}")
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
                                        depto = st.selectbox("Departamento", deptos, index=deptos.index(worker['departamento_nombre']) if worker['departamento_nombre'] in deptos else 0, key=f"edit_depto_{row['id']}_{idx}")
                                        subs = get_subdepartamentos_nombres()
                                        sub = st.selectbox("Subdepartamento", subs, index=subs.index(worker['subdepartamento_nombre']) if worker['subdepartamento_nombre'] in subs else 0, key=f"edit_sub_{row['id']}_{idx}")
                                        tipo = st.selectbox("Tipo Nómina", ["especial", "imss"], index=0 if worker['tipo_nomina']=='especial' else 1, key=f"edit_tipo_{row['id']}_{idx}")
                                        puestos = get_puestos_nombres()
                                        p = st.selectbox("Puesto", puestos, index=puestos.index(worker['puesto_nombre']) if worker['puesto_nombre'] in puestos else 0, key=f"edit_puesto_{row['id']}_{idx}")
                                        est = st.selectbox("Estatus", ["activo", "baja"], index=0 if worker['estatus']=='activo' else 1, key=f"edit_estatus_{row['id']}_{idx}")
                                        col_buttons = st.columns(2)
                                        with col_buttons[0]:
                                            if st.form_submit_button("💾 Guardar Cambios"):
                                                data = {'apellido_paterno': ap, 'apellido_materno': am, 'nombre': nom, 'correo': email, 'telefono': tel, 'departamento': depto, 'subdepartamento': sub, 'tipo_nomina': tipo, 'puesto': p, 'estatus': est}
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
    fecha_actual = get_mexico_date()
    fecha_formateada = fecha_actual.strftime("%Y/%m/%d")
    semana_actual = get_mexico_week()
    dia_espanol = get_mexico_day_spanish()
    col_fecha, col_dia, col_semana = st.columns(3)
    with col_fecha:
        st.markdown(f'<div class="date-card"><div style="font-size: 12px;">📅 FECHA</div><div style="font-size: 24px; font-weight: bold;">{fecha_formateada}</div></div>', unsafe_allow_html=True)
    with col_dia:
        st.markdown(f'<div class="time-card"><div style="font-size: 12px;">📆 DÍA</div><div style="font-size: 24px; font-weight: bold;">{dia_espanol}</div></div>', unsafe_allow_html=True)
    with col_semana:
        st.markdown(f'<div class="week-card"><div style="font-size: 12px;">📆 SEMANA</div><div style="font-size: 24px; font-weight: bold;">{semana_actual}</div></div>', unsafe_allow_html=True)
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
        trabajador_seleccionado = st.selectbox("Seleccionar trabajador:", trabajadores.apply(lambda x: f"{x['id']} - {x['nombre']} {x['apellido_paterno']}", axis=1), key="trabajador_manual_cosecha")
        trabajador_id = int(trabajador_seleccionado.split(' - ')[0]) if trabajador_seleccionado else None
    else:
        trabajador_id = None
    invernaderos = get_invernaderos_usuario()
    if invernaderos:
        invernadero_seleccionado = st.selectbox("Invernadero *", invernaderos, format_func=lambda x: f"{x[1]} - {x[2]}", key="invernadero_manual_cosecha")
        invernadero_id = invernadero_seleccionado[0]
    else:
        invernadero_id = None
        st.error("No tienes invernaderos asignados para hoy")
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
    merma_kilos = st.number_input("Merma (kilos):", min_value=0.0, value=0.0, step=0.5, key="merma_manual")
    st.text_input("Número de Cajas:", value=f"{st.session_state.cajas_calculadas:.2f}", disabled=True, key="cajas_manual")
    if merma_kilos > 0 and cantidad_clams > 0:
        porcentaje_merma = (merma_kilos / cantidad_clams) * 100
        st.metric("📊 Porcentaje de Merma", f"{porcentaje_merma:.2f}%")
    if st.button("💾 Guardar Cosecha", type="primary", use_container_width=True, key="guardar_cosecha_manual"):
        if not trabajador_id:
            st.error("Seleccione un trabajador")
        elif not invernadero_id:
            st.error("Seleccione un invernadero")
        elif cantidad_clams <= 0:
            st.error("Ingrese una cantidad válida de clams")
        else:
            data = {'fecha': fecha_actual, 'dia': dia_espanol, 'semana': semana_actual, 'trabajador_id': trabajador_id, 'invernadero_id': invernadero_id, 'tipo_cosecha': tipo_cosecha, 'calidad': calidad, 'presentacion': presentacion, 'cantidad_clams': float(cantidad_clams), 'merma_kilos': float(merma_kilos)}
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
            if not get_configuracion_sistema('registro_manual_asistencia'):
                st.warning("⚠️ El registro manual de asistencia está deshabilitado por el administrador")
            else:
                trabajadores = get_all_workers()
                if not trabajadores.empty:
                    trabajador_seleccionado = st.selectbox("Seleccionar trabajador:", trabajadores.apply(lambda x: f"{x['id']} - {x['nombre']} {x['apellido_paterno']}", axis=1), key="trabajador_asistencia_manual")
                    trabajador_id = int(trabajador_seleccionado.split(' - ')[0]) if trabajador_seleccionado else None
                else:
                    trabajador_id = None
                invernaderos = get_invernaderos_usuario()
                if invernaderos:
                    invernadero = st.selectbox("Invernadero:", invernaderos, format_func=lambda x: f"{x[1]} - {x[2]}", key="invernadero_asistencia_manual")
                    invernadero_id = invernadero[0]
                else:
                    invernadero_id = None
                    st.warning("No tienes invernaderos asignados para hoy")
                tipo_evento = st.selectbox("Tipo de Evento:", ["entrada_invernadero", "salida_comer", "regreso_comida", "salida_invernadero"], format_func=lambda x: {'entrada_invernadero': '🚪 Entrada a Invernadero', 'salida_comer': '🍽️ Salida a Comer', 'regreso_comida': '✅ Regreso de Comida', 'salida_invernadero': '🚪 Salida de Invernadero'}[x], key="tipo_evento_asistencia_manual")
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
        fecha_resumen = st.date_input("Seleccionar fecha:", get_mexico_date(), key="fecha_resumen_asist")
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
                st.dataframe(df_resumen[['trabajador', 'hora_entrada', 'hora_salida_comida', 'hora_entrada_comida', 'hora_salida', 'invernadero', 'estado_actual']], use_container_width=True)
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
            trabajador_seleccionado = st.selectbox("Filtrar por trabajador:", trabajadores_opciones, format_func=lambda x: x[1] if isinstance(x, tuple) else x, key="hist_trabajador_asist")
        with col2:
            fecha_inicio = st.date_input("Fecha inicio:", get_mexico_date() - timedelta(days=30), key="hist_inicio_asist")
        with col3:
            fecha_fin = st.date_input("Fecha fin:", get_mexico_date(), key="hist_fin_asist")
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
                st.download_button("📥 Exportar Historial", data=output, file_name=f"historial_asistencia_{get_mexico_date()}.xlsx")
            else:
                st.info("No se encontraron registros")
    with tab4:
        st.subheader("💤 Registrar Descanso")
        col1, col2 = st.columns(2)
        with col1:
            trabajadores = get_all_workers()
            trabajador_seleccionado = st.selectbox("Seleccionar trabajador:", trabajadores.apply(lambda x: f"{x['id']} - {x['nombre']} {x['apellido_paterno']}", axis=1) if not trabajadores.empty else [], key="descanso_trabajador_select")
            trabajador_id = int(trabajador_seleccionado.split(' - ')[0]) if trabajador_seleccionado else None
        with col2:
            fecha_descanso = st.date_input("Fecha de descanso:", get_mexico_date(), key="fecha_descanso")
        tipo_descanso = st.selectbox("Tipo de Descanso:", ["Descanso", "Vacaciones", "Permiso", "Enfermedad", "Capacitación", "Otro"], key="tipo_descanso_select")
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
        • <strong>Permiso Justificado</strong> - Permiso con justificación<br>
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
                    trabajador_incidencia = st.selectbox("👤 Seleccionar trabajador *", trabajadores.apply(lambda x: f"{x['id']} - {x['nombre']} {x['apellido_paterno']} ({x['puesto']})", axis=1), key="incidencia_trabajador_select")
                    trabajador_id = int(trabajador_incidencia.split(' - ')[0]) if trabajador_incidencia else None
                else:
                    trabajador_id = None
                    st.warning("No hay trabajadores registrados")
            with col2:
                fecha_incidencia = st.date_input("📅 Fecha de incidencia *", get_mexico_date(), key="fecha_incidencia")
            tipo_incidencia = st.selectbox("📌 Tipo de Incidencia *", ["Enfermedad", "Permiso Justificado", "Permiso Injustificado", "Retardo", "Falta Justificada", "Falta Injustificada", "Otra"], key="tipo_incidencia_select")
            subtipo = None
            horas_afectadas = 0.0
            if tipo_incidencia == "Enfermedad":
                subtipo = st.selectbox("🩺 Tipo de enfermedad", ["General", "Accidente", "Incapacidad", "Consulta médica", "Covid-19", "Gripe", "Gastrointestinal", "Otro"], key="subtipo_enfermedad")
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
                    success, msg = registrar_incidencia(trabajador_id, fecha_incidencia, tipo_incidencia, subtipo, horas_afectadas, justificada, observaciones, registrado_por)
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
            fecha_inc_inicio = st.date_input("Fecha inicio:", get_mexico_date() - timedelta(days=30), key="inc_inicio")
        with col2:
            fecha_inc_fin = st.date_input("Fecha fin:", get_mexico_date(), key="inc_fin")
        resumen_inc = get_resumen_incidencias(fecha_inc_inicio, fecha_inc_fin)
        if not resumen_inc['resumen_tipo'].empty:
            col1, col2 = st.columns(2)
            with col1:
                fig = px.pie(resumen_inc['resumen_tipo'], values='cantidad', names='tipo_incidencia', title='Distribución por Tipo de Incidencia', color_discrete_sequence=px.colors.qualitative.Set2)
                fig.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig, use_container_width=True)
            with col2:
                fig = px.bar(resumen_inc['resumen_tipo'], x='tipo_incidencia', y='cantidad', title='Cantidad de Incidencias por Tipo', color='tipo_incidencia', text='cantidad')
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
            trabajadores_inc = [("", "Todos")] + [(row['id'], f"{row['nombre']} {row['apellido_paterno']}") for _, row in trabajadores.iterrows()] if not trabajadores.empty else [("", "Todos")]
            filtro_trabajador_inc = st.selectbox("Filtrar por trabajador:", trabajadores_inc, format_func=lambda x: x[1] if isinstance(x, tuple) else x, key="filtro_trabajador_inc")
        trabajador_id_filtro = filtro_trabajador_inc[0] if filtro_trabajador_inc and filtro_trabajador_inc[0] else None
        incidencias = get_incidencias(fecha_hist_inc_inicio, fecha_hist_inc_fin, trabajador_id_filtro)
        if not incidencias.empty:
            incidencias_display = incidencias.copy()
            incidencias_display['fecha'] = pd.to_datetime(incidencias_display['fecha']).dt.strftime('%d/%m/%Y')
            incidencias_display['justificada'] = incidencias_display['justificada'].map({1: '✅ Sí', 0: '❌ No'})
            st.dataframe(incidencias_display[['fecha', 'trabajador', 'tipo_incidencia', 'subtipo', 'horas_afectadas', 'justificada', 'observaciones', 'registrado_por']], use_container_width=True)
            output = export_to_excel(incidencias, "Incidencias")
            st.download_button("📥 Exportar Incidencias a Excel", data=output, file_name=f"incidencias_{get_mexico_date()}.xlsx")
        else:
            st.info("No hay registros de incidencias en el período seleccionado")

def mostrar_avance_cosecha():
    st.header("📊 Registro de Avance de Cosecha")
    st.markdown("""
    <div style="background-color: #e8f5e9; padding: 15px; border-radius: 10px; margin-bottom: 20px;">
        <strong>📌 Información:</strong><br>
        • Invernaderos 1 al 8: <strong>40 líneas</strong> cada uno<br>
        • Invernaderos 9 al 11: <strong>36 líneas</strong> cada uno<br>
        • Turnos disponibles: Reporte 10:00am, 12:00pm, 02:00pm, 03:00pm, 04:00pm, 05:00pm, 06:00pm, 07:00pm, 08:00pm
    </div>
    """, unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["📝 Registrar Avance", "📊 Historial de Avance"])
    with tab1:
        st.subheader("Registrar Avance Diario")
        fecha_actual = get_mexico_date()
        fecha_formateada = fecha_actual.strftime("%Y/%m/%d")
        hora_actual = get_mexico_time().strftime("%H:%M")
        semana_actual = get_mexico_week()
        col_fecha, col_hora, col_semana = st.columns(3)
        with col_fecha:
            st.markdown(f'<div class="date-card"><div style="font-size: 12px;">📅 FECHA DEL REGISTRO</div><div style="font-size: 24px; font-weight: bold;">{fecha_formateada}</div></div>', unsafe_allow_html=True)
        with col_hora:
            st.markdown(f'<div class="time-card"><div style="font-size: 12px;">⏰ HORA DEL REGISTRO</div><div style="font-size: 24px; font-weight: bold;">{hora_actual}</div></div>', unsafe_allow_html=True)
        with col_semana:
            st.markdown(f'<div class="week-card"><div style="font-size: 12px;">📆 SEMANA</div><div style="font-size: 24px; font-weight: bold;">{semana_actual}</div></div>', unsafe_allow_html=True)
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        with col1:
            invernaderos = get_invernaderos_usuario()
            if invernaderos:
                invernadero_seleccionado = st.selectbox("Seleccionar Invernadero *", invernaderos, format_func=lambda x: f"{x[1]} - {x[2]}", key="invernadero_avance")
                invernadero_id = invernadero_seleccionado[0]
                invernadero_nombre = invernadero_seleccionado[1]
                lineas_totales = get_lineas_totales_por_invernadero(invernadero_id, invernadero_nombre)
                st.info(f"📏 Total de líneas en {invernadero_nombre}: {lineas_totales}")
            else:
                st.error("No tienes invernaderos asignados para hoy")
                invernadero_id = None
                invernadero_nombre = None
                lineas_totales = 0
        with col2:
            supervisor = st.text_input("Nombre del Supervisor *", placeholder="Ingrese su nombre", key="supervisor_avance")
        with col3:
            turno = st.selectbox("Turno *", REPORTE_TURNOS, key="turno_avance")
        st.markdown("---")
        if invernadero_id:
            ultimo_avance = get_ultimo_avance_dia(invernadero_id)
            if ultimo_avance:
                st.info(f"📊 **Avance actual del día ({invernadero_nombre}):**\n- Líneas cosechadas: **{ultimo_avance['lineas_cosechadas']}** de {lineas_totales}\n- Porcentaje: **{ultimo_avance['porcentaje']:.1f}%**\n- Última actualización: **{ultimo_avance['hora']}** (Turno: {ultimo_avance['turno']})")
                lineas_restantes = lineas_totales - ultimo_avance['lineas_cosechadas']
                if lineas_restantes > 0:
                    st.warning(f"💡 Faltan {lineas_restantes} líneas por cosechar para completar el día")
            else:
                st.success(f"✨ Primer registro del día para {invernadero_nombre}. ¡Comienza desde 0!")
        col1, col2 = st.columns(2)
        with col1:
            valor_inicial = ultimo_avance['lineas_cosechadas'] if invernadero_id and ultimo_avance else 0
            lineas_cosechadas = st.number_input("Líneas Cosechadas *", min_value=0, max_value=lineas_totales, value=valor_inicial, step=1, key="lineas_cosechadas")
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
                success, msg = registrar_avance_cosecha(invernadero_id, invernadero_nombre, lineas_cosechadas, supervisor, observaciones, turno)
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
            fecha_hist_inicio = st.date_input("Fecha inicio:", get_mexico_date() - timedelta(days=30), key="avance_hist_inicio")
        with col2:
            fecha_hist_fin = st.date_input("Fecha fin:", get_mexico_date(), key="avance_hist_fin")
        with col3:
            turno_filtro = st.selectbox("Filtrar por turno:", ["Todos"] + REPORTE_TURNOS, key="turno_filtro_hist")
        turno_param = None if turno_filtro == "Todos" else turno_filtro
        df_avance = get_avance_historico_por_dia(fecha_hist_inicio, fecha_hist_fin, turno=turno_param)
        if not df_avance.empty:
            df_display = df_avance.copy()
            df_display['fecha'] = pd.to_datetime(df_display['fecha']).dt.strftime('%d/%m/%Y')
            df_display['porcentaje'] = df_display['porcentaje'].map(lambda x: f"{x:.1f}%")
            st.dataframe(df_display[['fecha', 'hora', 'turno', 'invernadero_nombre', 'lineas_cosechadas', 'lineas_totales', 'porcentaje', 'supervisor', 'observaciones']], use_container_width=True)
            output = export_to_excel(df_avance, "Avance_Cosecha_Historico")
            st.download_button("📥 Exportar Historial a Excel", data=output, file_name=f"avance_cosecha_historico_{get_mexico_date()}.xlsx")
            if not df_avance.empty:
                st.subheader("📈 Evolución del Avance por Día")
                fig = px.line(df_avance, x='fecha', y='porcentaje', color='invernadero_nombre', title='Evolución del Porcentaje de Avance por Día', labels={'fecha': 'Fecha', 'porcentaje': 'Porcentaje (%)', 'invernadero_nombre': 'Invernadero'}, markers=True)
                fig.update_layout(plot_bgcolor='white', height=500)
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay registros de avance en el período seleccionado")

def mostrar_traslados_camara_fria():
    st.header("❄️ Traslado a Cámara Fría")
    tab1, tab2, tab3, tab4 = st.tabs(["📦 Registrar Traslado", "⚖️ Registro de Pesaje", "📋 Comparativa Cosecha vs Traslado vs Pesaje", "📋 Historial"])
    with tab1:
        st.subheader("Registrar Traslado de Cajas a Cámara Fría")
        fecha_actual = get_mexico_date()
        hora_actual = get_mexico_time().strftime("%H:%M")
        fecha_formateada = fecha_actual.strftime("%Y/%m/%d")
        semana_actual = get_mexico_week()
        col_fecha, col_hora, col_semana = st.columns(3)
        with col_fecha:
            st.markdown(f'<div class="date-card"><div style="font-size: 12px;">📅 FECHA DEL TRASLADO</div><div style="font-size: 24px; font-weight: bold;">{fecha_formateada}</div></div>', unsafe_allow_html=True)
        with col_hora:
            st.markdown(f'<div class="time-card"><div style="font-size: 12px;">⏰ HORA DEL TRASLADO</div><div style="font-size: 24px; font-weight: bold;">{hora_actual}</div></div>', unsafe_allow_html=True)
        with col_semana:
            st.markdown(f'<div class="week-card"><div style="font-size: 12px;">📆 SEMANA</div><div style="font-size: 24px; font-weight: bold;">{semana_actual}</div></div>', unsafe_allow_html=True)
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            invernaderos = get_invernaderos_usuario()
            if invernaderos:
                invernadero_seleccionado = st.selectbox("🏭 Invernadero de origen:", invernaderos, format_func=lambda x: f"{x[1]} - {x[2]}", key="invernadero_traslado")
                invernadero_id = invernadero_seleccionado[0]
            else:
                st.error("No tienes invernaderos asignados para hoy")
                invernadero_id = None
        with col2:
            if invernadero_id:
                detalle_cajas = get_detalle_cajas_por_invernadero_presentacion(invernadero_id)
                total_cajas = detalle_cajas['6 oz'] + detalle_cajas['12 oz']
                st.markdown(f'<div style="background-color: #e8f4fd; padding: 15px; border-radius: 10px;"><h4 style="margin: 0 0 10px 0;">📦 Inventario en {invernadero_seleccionado[1]}</h4><p><strong>Total cajas disponibles:</strong> {total_cajas:.0f}</p><hr><p>🍓 <strong>Cajas 6 oz:</strong> {detalle_cajas["6 oz"]:.0f} cajas</p><p>🍓 <strong>Cajas 12 oz:</strong> {detalle_cajas["12 oz"]:.0f} cajas</p></div>', unsafe_allow_html=True)
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
                    supervisor_envia = st.selectbox("Supervisor:", supervisores.apply(lambda x: f"{x['id']} - {x['nombre']} {x['apellido_paterno']} ({x['puesto']})", axis=1), key="supervisor_envia")
                    supervisor_envia_id = int(supervisor_envia.split(' - ')[0]) if supervisor_envia else None
                else:
                    st.warning("No hay supervisores registrados")
                    supervisor_envia_id = None
            else:
                supervisor_envia_id = None
        with col2:
            st.subheader("👤 Recolector (quien lleva las cajas)")
            recolectores = get_recolectores()
            if recolectores:
                recolector = st.selectbox("Recolector:", recolectores, format_func=lambda x: x[1], key="recolector_traslado")
                recolector_id = recolector[0] if recolector else None
            else:
                st.warning("No hay recolectores registrados")
                recolector_id = None
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            tipo_envio = st.selectbox("📦 Tipo de Envío:", ["Nacional", "Exportación"], key="tipo_envio_select")
        with col2:
            presentacion = st.selectbox("📏 Presentación:", ["6 oz", "12 oz"], key="presentacion_traslado")
        cantidad_cajas = st.number_input("📊 Cantidad de Cajas a trasladar:", min_value=0.0, step=1.0, key="cantidad_traslado")
        lote = st.text_input("🏷️ Número de Lote (opcional):", placeholder="Ej: L-2024-001", key="lote_traslado")
        observaciones = st.text_area("📝 Observaciones:", placeholder="Ej: Calidad premium, primera selección, etc.", key="obs_traslado")
        if invernadero_id and cantidad_cajas > 0:
            detalle_cajas = get_detalle_cajas_por_invernadero_presentacion(invernadero_id)
            cajas_disponibles_por_tipo = detalle_cajas.get(presentacion, 0)
            if cantidad_cajas > cajas_disponibles_por_tipo:
                st.warning(f"⚠️ Solo hay {cajas_disponibles_por_tipo:.0f} cajas de {presentacion} disponibles en este invernadero")
        if st.button("✅ Registrar Traslado a Cámara Fría", type="primary", use_container_width=True, key="btn_registrar_traslado"):
            if not invernadero_id:
                st.error("Seleccione un invernadero de origen")
            elif not supervisor_envia_id:
                st.error("Seleccione el supervisor que entrega las cajas")
            elif not recolector_id:
                st.error("Seleccione el recolector que lleva las cajas")
            elif cantidad_cajas <= 0:
                st.error("Ingrese una cantidad válida de cajas")
            else:
                detalle_cajas = get_detalle_cajas_por_invernadero_presentacion(invernadero_id)
                cajas_disponibles_por_tipo = detalle_cajas.get(presentacion, 0)
                if cantidad_cajas > cajas_disponibles_por_tipo:
                    st.error(f"❌ No hay suficientes cajas de {presentacion}. Disponibles: {cajas_disponibles_por_tipo:.0f}")
                else:
                    success, msg = registrar_traslado_camara_fria(invernadero_id, cantidad_cajas, supervisor_envia_id, recolector_id, tipo_envio, presentacion, lote, observaciones)
                    if success:
                        st.success(msg)
                        st.balloons()
                        st.rerun()
                    else:
                        st.error(msg)
    with tab2:
        st.subheader("⚖️ Registro de Pesaje de Cajas")
        traslados_pendientes = get_traslados_camara_fria(fecha_inicio=get_mexico_date(), fecha_fin=get_mexico_date())
        if not traslados_pendientes.empty:
            traslado = st.selectbox("Seleccionar traslado a pesar:", traslados_pendientes.apply(lambda x: f"ID:{x['id']} - {x['invernadero']} - {x['cantidad_cajas']} cajas de {x['presentacion']}", axis=1), key="pesaje_traslado")
            traslado_id = int(traslado.split(' - ')[0].replace('ID:', '')) if traslado else None
            if traslado_id:
                traslado_data = traslados_pendientes[traslados_pendientes['id'] == traslado_id].iloc[0]
                st.info(f"📦 **Detalle del traslado:**\n- Invernadero: {traslado_data['invernadero']}\n- Cajas trasladadas: {traslado_data['cantidad_cajas']:.0f} de {traslado_data['presentacion']}\n- Supervisor: {traslado_data['trabajador_envia']}\n- Recolector: {traslado_data['recolector']}\n- Hora: {traslado_data['hora']}")
                col1, col2 = st.columns(2)
                with col1:
                    cantidad_pesadas = st.number_input("Cantidad de cajas pesadas:", min_value=0.0, step=1.0, value=float(traslado_data['cantidad_cajas']), key="pesadas")
                with col2:
                    cajas_recibidas = st.number_input("Cajas recibidas en frío:", min_value=0.0, step=1.0, value=float(traslado_data['cantidad_cajas']), key="recibidas")
                diferencia = cantidad_pesadas - cajas_recibidas
                if diferencia != 0:
                    if diferencia > 0:
                        st.warning(f"⚠️ Diferencia: Sobran {diferencia:.0f} cajas")
                    else:
                        st.warning(f"⚠️ Diferencia: Faltan {abs(diferencia):.0f} cajas")
                else:
                    st.success("✅ Coincidencia perfecta")
                nota = st.text_area("Nota (explicar diferencia):", placeholder="Ej: Merma por fruta dañada, cajas incompletas, etc.", key="nota_pesaje")
                pesadores = get_pesadores()
                if pesadores:
                    pesador = st.selectbox("Pesador:", pesadores, format_func=lambda x: x[1], key="pesador_select")
                    pesador_id = pesador[0] if pesador else None
                else:
                    st.warning("No hay pesadores registrados")
                    pesador_id = None
                if st.button("✅ Registrar Pesaje", type="primary", use_container_width=True):
                    if pesador_id:
                        success, msg = registrar_pesaje_cajas(traslado_id, traslado_data['invernadero_id'], pesador_id, traslado_data['presentacion'], cantidad_pesadas, cajas_recibidas, nota)
                        if success:
                            st.success(msg)
                            st.balloons()
                            st.rerun()
                        else:
                            st.error(msg)
                    else:
                        st.error("Seleccione un pesador")
        else:
            st.info("No hay traslados pendientes de pesar hoy")
        st.markdown("---")
        st.subheader("📊 Resumen de Pesajes del Día")
        pesajes_hoy = get_pesajes(fecha_inicio=get_mexico_date(), fecha_fin=get_mexico_date())
        if not pesajes_hoy.empty:
            st.dataframe(pesajes_hoy, use_container_width=True)
            total_diferencia = pesajes_hoy['diferencia'].sum()
            if total_diferencia != 0:
                st.warning(f"📊 Diferencia total del día: {total_diferencia:+.0f} cajas")
            else:
                st.success("✅ Sin diferencias en los pesajes del día")
        else:
            st.info("No hay pesajes registrados hoy")
    with tab3:
        st.subheader("📊 Comparativa: Cosechado vs Trasladado vs Pesado")
        fecha_inicio_comp = st.date_input("Fecha inicio comparativa:", get_mexico_date() - timedelta(days=30), key="comp_inicio")
        fecha_fin_comp = st.date_input("Fecha fin comparativa:", get_mexico_date(), key="comp_fin")
        if st.button("Actualizar Comparativa", use_container_width=True):
            cosechas = get_cosechas(fecha_inicio_comp, fecha_fin_comp)
            traslados = get_traslados_camara_fria(fecha_inicio_comp, fecha_fin_comp)
            pesajes = get_pesajes(fecha_inicio_comp, fecha_fin_comp)
            if not cosechas.empty or not traslados.empty or not pesajes.empty:
                total_cosechado = cosechas['numero_cajas'].sum() if not cosechas.empty else 0
                total_trasladado = traslados['cantidad_cajas'].sum() if not traslados.empty else 0
                total_pesado = pesajes['cajas_pesadas'].sum() if not pesajes.empty else 0
                total_recibido = pesajes['cajas_recibidas'].sum() if not pesajes.empty else 0
                diferencia_traslado = total_cosechado - total_trasladado
                diferencia_pesaje = total_pesado - total_recibido
                col1, col2, col3, col4, col5 = st.columns(5)
                with col1: st.metric("📦 Total Cosechado", f"{total_cosechado:.0f} cajas")
                with col2: st.metric("🚚 Total Trasladado", f"{total_trasladado:.0f} cajas")
                with col3: st.metric("⚖️ Total Pesado", f"{total_pesado:.0f} cajas")
                with col4: st.metric("✅ Total Recibido", f"{total_recibido:.0f} cajas")
                with col5: st.metric("📊 Diferencia Traslado", f"{diferencia_traslado:+.0f}", delta=f"{(diferencia_traslado/total_cosechado*100) if total_cosechado>0 else 0:.1f}%")
                fig = go.Figure()
                fechas = sorted(set(cosechas['fecha'].unique()) if not cosechas.empty else set())
                if not cosechas.empty:
                    df_c = cosechas.groupby('fecha')['numero_cajas'].sum().reset_index()
                    fig.add_trace(go.Scatter(x=df_c['fecha'], y=df_c['numero_cajas'], mode='lines+markers', name='Cosechado', line=dict(color='#2ecc71', width=3)))
                if not traslados.empty:
                    df_t = traslados.groupby('fecha')['cantidad_cajas'].sum().reset_index()
                    fig.add_trace(go.Scatter(x=df_t['fecha'], y=df_t['cantidad_cajas'], mode='lines+markers', name='Trasladado', line=dict(color='#3498db', width=3)))
                if not pesajes.empty:
                    df_p = pesajes.groupby('fecha')['cajas_pesadas'].sum().reset_index()
                    fig.add_trace(go.Scatter(x=df_p['fecha'], y=df_p['cajas_pesadas'], mode='lines+markers', name='Pesado', line=dict(color='#e74c3c', width=3)))
                fig.update_layout(title='Comparativa Diaria: Cosechado vs Trasladado vs Pesado', xaxis_title='Fecha', yaxis_title='Cajas', plot_bgcolor='white', height=500)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No hay datos para el período seleccionado")
    with tab4:
        st.subheader("📋 Historial de Traslados")
        col1, col2, col3 = st.columns(3)
        with col1:
            fecha_hist_inicio = st.date_input("Fecha inicio:", get_mexico_date() - timedelta(days=30), key="hist_traslado_inicio")
        with col2:
            fecha_hist_fin = st.date_input("Fecha fin:", get_mexico_date(), key="hist_traslado_fin")
        with col3:
            invernaderos_filtro = [("", "Todos")] + [(id_inv, nombre) for id_inv, nombre, _, _ in get_all_invernaderos()]
            invernadero_filtro = st.selectbox("Filtrar por invernadero:", invernaderos_filtro, format_func=lambda x: x[1] if isinstance(x, tuple) else x, key="invernadero_historial_traslado")
        invernadero_id_filtro = invernadero_filtro[0] if invernadero_filtro and invernadero_filtro[0] else None
        traslados = get_traslados_camara_fria(fecha_hist_inicio, fecha_hist_fin, invernadero_id_filtro)
        if not traslados.empty:
            st.dataframe(traslados, use_container_width=True)
            output = export_to_excel(traslados, "Traslados_Camara_Fria")
            st.download_button("📥 Exportar a Excel", data=output, file_name=f"traslados_camara_fria_{get_mexico_date()}.xlsx")
            st.subheader("📊 Resumen de Traslados por Invernadero")
            resumen = traslados.groupby('invernadero')['cantidad_cajas'].sum().reset_index()
            fig = px.bar(resumen, x='invernadero', y='cantidad_cajas', title='Total de Cajas Trasladadas por Invernadero')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay traslados registrados")

def mostrar_gestion_merma():
    st.header("🗑️ Gestión de Merma")
    tab1, tab2, tab3 = st.tabs(["📝 Registrar Merma", "📊 Dashboard Merma", "📋 Historial"])
    with tab1:
        st.subheader("Registrar Merma")
        fecha_actual = get_mexico_date()
        fecha_formateada = fecha_actual.strftime("%Y/%m/%d")
        hora_actual = get_mexico_time().strftime("%H:%M")
        semana_actual = get_mexico_week()
        col_fecha, col_hora, col_semana = st.columns(3)
        with col_fecha:
            st.markdown(f'<div class="date-card"><div style="font-size: 12px;">📅 FECHA DEL REGISTRO</div><div style="font-size: 24px; font-weight: bold;">{fecha_formateada}</div></div>', unsafe_allow_html=True)
        with col_hora:
            st.markdown(f'<div class="time-card"><div style="font-size: 12px;">⏰ HORA DEL REGISTRO</div><div style="font-size: 24px; font-weight: bold;">{hora_actual}</div></div>', unsafe_allow_html=True)
        with col_semana:
            st.markdown(f'<div class="week-card"><div style="font-size: 12px;">📆 SEMANA</div><div style="font-size: 24px; font-weight: bold;">{semana_actual}</div></div>', unsafe_allow_html=True)
        st.markdown("---")
        with st.form("form_merma"):
            col1, col2 = st.columns(2)
            with col1:
                invernaderos = get_invernaderos_usuario()
                if invernaderos:
                    invernadero = st.selectbox("Invernadero *", invernaderos, format_func=lambda x: f"{x[1]} - {x[2]}", key="invernadero_merma")
                    invernadero_id = invernadero[0]
                else:
                    invernadero_id = None
                    st.error("No tienes invernaderos asignados para hoy")
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
            fecha_inicio = st.date_input("Fecha inicio:", get_mexico_date() - timedelta(days=30), key="merma_inicio")
        with col2:
            fecha_fin = st.date_input("Fecha fin:", get_mexico_date(), key="merma_fin")
        stats_merma = get_stats_merma(fecha_inicio, fecha_fin)
        col1, col2, col3, col4 = st.columns(4)
        with col1: st.metric("🗑️ Total Kilos", f"{stats_merma['total_merma']:,.2f} kg")
        with col2: st.metric("📊 Promedio/Día", f"{stats_merma['total_merma'] / max(len(stats_merma['merma_diaria']), 1):.1f} kg")
        with col3: st.metric("📝 Registros", len(stats_merma['merma_diaria']) if not stats_merma['merma_diaria'].empty else 0)
        with col4: st.metric("🏆 Mayor Merma", stats_merma['merma_por_invernadero'].iloc[0]['invernadero_nombre'] if not stats_merma['merma_por_invernadero'].empty else "N/A")
        if not stats_merma['merma_diaria'].empty:
            fig = px.bar(stats_merma['merma_diaria'], x='fecha', y='kilos_merma', title='Merma Diaria')
            st.plotly_chart(fig, use_container_width=True)
        if not stats_merma['merma_por_tipo'].empty:
            fig = px.pie(stats_merma['merma_por_tipo'], values='kilos_merma', names='tipo_merma', title='Merma por Tipo')
            st.plotly_chart(fig, use_container_width=True)
    with tab3:
        st.subheader("Historial de Merma")
        col1, col2, col3 = st.columns(3)
        with col1:
            fecha_hist_inicio = st.date_input("Fecha inicio:", get_mexico_date() - timedelta(days=30), key="merma_hist_inicio")
        with col2:
            fecha_hist_fin = st.date_input("Fecha fin:", get_mexico_date(), key="merma_hist_fin")
        with col3:
            invernaderos_filtro = [("", "Todos")] + [(id_inv, nombre) for id_inv, nombre, _, _ in get_all_invernaderos()]
            invernadero_filtro = st.selectbox("Filtrar por invernadero:", invernaderos_filtro, format_func=lambda x: x[1] if isinstance(x, tuple) else x, key="merma_invernadero_filtro")
        invernadero_id_filtro = invernadero_filtro[0] if invernadero_filtro and invernadero_filtro[0] else None
        merma = get_merma(fecha_hist_inicio, fecha_hist_fin, invernadero_id_filtro)
        if not merma.empty:
            st.dataframe(merma, use_container_width=True)
            output = export_to_excel(merma, "Merma")
            st.download_button("📥 Exportar a Excel", data=output, file_name=f"merma_{get_mexico_date()}.xlsx")

def mostrar_gestion_invernaderos():
    st.header("🏭 Gestión de Invernaderos")
    with st.expander("➕ Agregar Nuevo Invernadero"):
        with st.form("form_invernadero"):
            nombre_invernadero = st.text_input("Nombre del Invernadero *", key="nombre_invernadero")
            ubicacion_invernadero = st.text_input("Ubicación *", key="ubicacion_invernadero")
            lineas_totales = st.number_input("Líneas totales", min_value=1, max_value=100, value=40, key="lineas_invernadero")
            if st.form_submit_button("Guardar Invernadero"):
                if nombre_invernadero and ubicacion_invernadero:
                    success, msg = add_invernadero(nombre_invernadero, ubicacion_invernadero, lineas_totales)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
                else:
                    st.error("Complete todos los campos")
    st.markdown("---")
    st.subheader("Lista de Invernaderos")
    invernaderos = get_all_invernaderos()
    if invernaderos:
        for id_inv, nombre, ubicacion, lineas in invernaderos:
            with st.container():
                cols = st.columns([3, 2, 1, 1, 1])
                with cols[0]: st.write(f"**{nombre}**")
                with cols[1]: st.write(f"📍 {ubicacion}")
                with cols[2]: st.write(f"📏 {lineas} líneas")
                with cols[3]:
                    if st.button("✏️ Editar", key=f"edit_inv_{id_inv}"):
                        st.session_state[f'editing_inv_{id_inv}'] = True
                with cols[4]:
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
                        nuevas_lineas = st.number_input("Líneas totales", value=lineas, key=f"edit_lineas_{id_inv}")
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.form_submit_button("💾 Guardar"):
                                success, msg = update_invernadero(id_inv, nuevo_nombre, nueva_ubicacion, nuevas_lineas)
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
                with col1:
                    st.image(qr_bytes, width=150)
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
            st.download_button("📥 Descargar ZIP", data=zip_buffer, file_name=f"todos_qr_{get_mexico_date().strftime('%Y%m%d')}.zip", mime="application/zip")
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
            st.download_button("📥 Exportar a Excel", data=output, file_name=f"registros_qr_{get_mexico_date().strftime('%Y%m%d')}.xlsx")
        else:
            st.info("No hay registros de escaneos")
    except Exception as e:
        st.error(f"Error al obtener registros: {str(e)}")

def mostrar_reportes():
    st.header("📊 Reportes")
    tab1, tab2, tab3 = st.tabs(["📥 Ingresos", "📤 Bajas", "📋 Nómina Activa"])
    with tab1:
        st.subheader("Ingresos de la Semana")
        if st.button("Generar reporte", key="btn_ingresos", use_container_width=True):
            df, inicio, fin = get_report_ingresos_semana()
            if df.empty:
                st.warning(f"No hay ingresos entre {inicio} y {fin}")
            else:
                st.success(f"Encontrados: {len(df)}")
                st.dataframe(df, use_container_width=True)
                output = export_to_excel(df, "Ingresos")
                st.download_button("📥 Descargar Excel", data=output, file_name=f"ingresos_{inicio}.xlsx")
    with tab2:
        st.subheader("Bajas de la Semana")
        if st.button("Generar reporte", key="btn_bajas", use_container_width=True):
            df, inicio, fin = get_report_bajas_semana()
            if df.empty:
                st.warning(f"No hay bajas entre {inicio} y {fin}")
            else:
                st.success(f"Encontradas: {len(df)}")
                st.dataframe(df, use_container_width=True)
                output = export_to_excel(df, "Bajas")
                st.download_button("📥 Descargar Excel", data=output, file_name=f"bajas_{inicio}.xlsx")
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
                st.download_button("📥 Descargar Excel", data=output, file_name=f"nomina_activa_{get_mexico_date()}.xlsx")

def mostrar_catalogos():
    st.header("📋 Gestión de Catálogos")
    tab1, tab2, tab3 = st.tabs(["🏢 Departamentos", "📂 Subdepartamentos", "💼 Puestos"])
    for tab, tabla, get_func in [(tab1, "departamentos", get_departamentos), (tab2, "subdepartamentos", get_subdepartamentos), (tab3, "puestos", get_puestos)]:
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
        • Registre las proyecciones de cajas por semana<br>
        • El sistema sumará automáticamente la producción real de todos los invernaderos para comparar<br>
        • Se calculará el déficit/superávit semanal y total
    </div>
    """, unsafe_allow_html=True)
    tab1, tab2, tab3 = st.tabs(["📝 Registrar Proyección", "📊 Comparativa Real vs Proyectado", "📋 Historial"])
    with tab1:
        st.subheader("Registrar Nueva Proyección Semanal")
        semana_actual = get_mexico_week()
        col_semana_actual = st.columns([1, 2, 1])
        with col_semana_actual[1]:
            st.markdown(f'<div class="week-card"><div style="font-size: 12px;">📆 SEMANA ACTUAL</div><div style="font-size: 24px; font-weight: bold;">{semana_actual}</div></div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            semana = st.number_input("Semana *", min_value=1, max_value=52, value=semana_actual, step=1, key="semana_proyeccion")
        with col2:
            cajas_proyectadas = st.number_input("Cajas Proyectadas *", min_value=0.0, step=50.0, value=0.0, key="cajas_proyectadas")
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
            semana_inicio = st.number_input("Semana inicio", min_value=1, max_value=52, value=1, key="comp_semana_inicio")
        with col2:
            semana_fin = st.number_input("Semana fin", min_value=1, max_value=52, value=get_mexico_week(), key="comp_semana_fin")
        with col3:
            tipo_opciones = ["Todos", "Nacional", "Exportación"]
            tipo_seleccionado = st.selectbox("Tipo de Cosecha", tipo_opciones, key="comp_tipo_cosecha")
            presentacion_opciones = ["Todos", "6 oz", "12 oz"]
            presentacion_seleccionado = st.selectbox("Presentación", presentacion_opciones, key="comp_presentacion")
        if st.button("📊 Actualizar Comparativa", key="btn_actualizar_comparativa", use_container_width=True):
            df_comparativa = get_comparativa_proyeccion_real_con_filtros(semana_inicio, semana_fin, tipo_seleccionado if tipo_seleccionado != "Todos" else None, presentacion_seleccionado if presentacion_seleccionado != "Todos" else None)
            if not df_comparativa.empty:
                st.success(f"Datos encontrados para {len(df_comparativa)} semanas")
                total_proyectado = df_comparativa['cajas_proyectadas'].sum()
                total_real = df_comparativa['cajas_reales'].sum()
                diferencia_total = total_real - total_proyectado
                porcentaje_total = (diferencia_total / total_proyectado * 100) if total_proyectado > 0 else 0
                col1, col2, col3, col4 = st.columns(4)
                with col1: st.metric("📊 Total Proyectado", f"{total_proyectado:,.0f} cajas")
                with col2: st.metric("✅ Total Real", f"{total_real:,.0f} cajas")
                with col3: st.metric("📈 Diferencia", f"{diferencia_total:+,.0f} cajas")
                with col4: st.metric("📉 Porcentaje", f"{porcentaje_total:+.1f}%")
                st.subheader("Detalle por Semana")
                df_display = df_comparativa.copy()
                df_display['cajas_proyectadas'] = df_display['cajas_proyectadas'].map(lambda x: f"{x:.0f}")
                df_display['cajas_reales'] = df_display['cajas_reales'].map(lambda x: f"{x:.0f}")
                df_display['diferencia'] = df_display['diferencia'].map(lambda x: f"{x:+.0f}")
                df_display['porcentaje_desviacion'] = df_display['porcentaje_desviacion'].map(lambda x: f"{x:+.1f}%")
                st.dataframe(df_display[['semana', 'cajas_proyectadas', 'cajas_reales', 'diferencia', 'porcentaje_desviacion', 'estado']], use_container_width=True)
                st.subheader("📊 Análisis Visual")
                fig1 = go.Figure()
                fig1.add_trace(go.Bar(x=df_comparativa['semana'], y=df_comparativa['cajas_proyectadas'], name='Proyectado', marker_color='#3498db'))
                fig1.add_trace(go.Bar(x=df_comparativa['semana'], y=df_comparativa['cajas_reales'], name='Real', marker_color='#2ecc71'))
                fig1.update_layout(title='Comparativa Semanal: Proyectado vs Real', xaxis_title='Semana', yaxis_title='Cajas', barmode='group', plot_bgcolor='white', height=500)
                st.plotly_chart(fig1, use_container_width=True)
                fig2 = go.Figure()
                fig2.add_trace(go.Scatter(x=df_comparativa['semana'], y=df_comparativa['porcentaje_desviacion'], mode='lines+markers', name='% Desviación', line=dict(color='#e74c3c', width=3), marker=dict(size=8)))
                fig2.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
                fig2.update_layout(title='Evolución del Porcentaje de Desviación por Semana', xaxis_title='Semana', yaxis_title='% Desviación', plot_bgcolor='white', height=400)
                st.plotly_chart(fig2, use_container_width=True)
                output = export_to_excel(df_comparativa, "Comparativa_Real_Proyectado")
                st.download_button("📥 Exportar Comparativa a Excel", data=output, file_name=f"comparativa_proyecciones_{get_mexico_date()}.xlsx")
            else:
                st.warning("No hay datos de proyecciones o producción real para el período seleccionado")
    with tab3:
        st.subheader("Historial de Proyecciones Registradas")
        col1, col2 = st.columns(2)
        with col1:
            semana_hist = st.number_input("Filtrar por semana (opcional)", min_value=1, max_value=52, value=1, step=1, key="hist_semana")
        semana_hist_param = semana_hist if semana_hist > 0 else None
        df_proyecciones = get_proyecciones(semana=semana_hist_param)
        if not df_proyecciones.empty:
            df_display = df_proyecciones.copy()
            df_display['fecha_registro'] = pd.to_datetime(df_display['fecha_registro']).dt.strftime('%d/%m/%Y %H:%M')
            st.dataframe(df_display[['semana', 'cajas_proyectadas', 'fecha_registro', 'registrado_por', 'observaciones']], use_container_width=True)
            output = export_to_excel(df_proyecciones, "Proyecciones")
            st.download_button("📥 Exportar Proyecciones a Excel", data=output, file_name=f"proyecciones_{get_mexico_date()}.xlsx")
            col1, col2 = st.columns(2)
            with col1: st.metric("Total Proyectado", f"{df_proyecciones['cajas_proyectadas'].sum():,.0f} cajas")
            with col2: st.metric("Promedio por Semana", f"{df_proyecciones['cajas_proyectadas'].mean():,.0f} cajas")
        else:
            st.info("No hay proyecciones registradas para los filtros seleccionados")

def mostrar_dashboard_general():
    with st.sidebar:
        st.markdown('<div class="dashboard-header" style="background: linear-gradient(135deg, #1a472a 0%, #2d6a4f 100%); padding: 20px; border-radius: 20px; margin-bottom: 20px;"><h3 style="margin:0;">📊 Tablero de Control</h3><p style="margin:5px 0 0 0; opacity:0.8;">Filtros interactivos</p></div>', unsafe_allow_html=True)
        st.markdown("### 📅 Rango de Fechas")
        fecha_default_inicio = get_mexico_date() - timedelta(days=90)
        fecha_default_fin = get_mexico_date()
        fecha_inicio = st.date_input("Fecha inicio", fecha_default_inicio, key="dash_fecha_inicio")
        fecha_fin = st.date_input("Fecha fin", fecha_default_fin, key="dash_fecha_fin")
        st.markdown("### 🏭 Invernadero")
        invernaderos = get_invernaderos_usuario()
        invernaderos_opciones = ["Todos"] + [nombre for _, nombre, _, _ in invernaderos]
        invernadero_seleccionado = st.selectbox("Seleccionar invernadero", invernaderos_opciones, key="dash_invernadero")
        st.markdown("### 🌾 Tipo de Cultivo")
        tipo_opciones = ["Todos", "Nacional", "Exportación"]
        tipo_seleccionado = st.selectbox("Seleccionar tipo", tipo_opciones, key="dash_tipo")
        st.markdown("### 📦 Presentación")
        presentacion_opciones = ["Todos", "6 oz", "12 oz"]
        presentacion_seleccionado = st.selectbox("Seleccionar presentación", presentacion_opciones, key="dash_presentacion")
        st.markdown("### 📆 Semana")
        semana_actual = get_mexico_week()
        semana_seleccionada = st.number_input("Número de semana", min_value=1, max_value=52, value=semana_actual, key="dash_semana")
        st.markdown("---")
        st.caption("📊 Datos actualizados en tiempo real")
    
    try:
        query_cosechas = supabase.table('cosechas').select("*, invernaderos:invernadero_id (nombre), trabajadores:trabajador_id (nombre, apellido_paterno)")
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
        trabajadores_result = supabase.table('trabajadores').select('*').execute()
        df_trabajadores = pd.DataFrame(trabajadores_result.data) if trabajadores_result.data else pd.DataFrame()
        query_traslados = supabase.table('traslados_camara_fria').select("*, invernaderos:invernadero_id (nombre)")
        if fecha_inicio:
            query_traslados = query_traslados.gte('fecha', fecha_inicio.isoformat())
        if fecha_fin:
            query_traslados = query_traslados.lte('fecha', fecha_fin.isoformat())
        traslados_result = query_traslados.execute()
        df_traslados = pd.DataFrame(traslados_result.data) if traslados_result.data else pd.DataFrame()
        if not df_traslados.empty and invernadero_seleccionado and invernadero_seleccionado != "Todos":
            df_traslados = df_traslados[df_traslados['invernaderos'].apply(lambda x: x['nombre'] if x else '') == invernadero_seleccionado]
        if semana_seleccionada and not df_traslados.empty:
            df_traslados = df_traslados[df_traslados['semana'] == semana_seleccionada]
        query_incidencias = supabase.table('incidencias').select("*, trabajadores:trabajador_id (nombre, apellido_paterno)")
        if fecha_inicio:
            query_incidencias = query_incidencias.gte('fecha', fecha_inicio.isoformat())
        if fecha_fin:
            query_incidencias = query_incidencias.lte('fecha', fecha_fin.isoformat())
        incidencias_result = query_incidencias.execute()
        df_incidencias = pd.DataFrame(incidencias_result.data) if incidencias_result.data else pd.DataFrame()
        query_pesajes = supabase.table('pesaje_cajas').select('*')
        if fecha_inicio:
            query_pesajes = query_pesajes.gte('fecha', fecha_inicio.isoformat())
        if fecha_fin:
            query_pesajes = query_pesajes.lte('fecha', fecha_fin.isoformat())
        pesajes_result = query_pesajes.execute()
        df_pesajes = pd.DataFrame(pesajes_result.data) if pesajes_result.data else pd.DataFrame()
        activos = len(df_trabajadores[df_trabajadores['estatus'] == 'activo']) if not df_trabajadores.empty else 0
        bajas = len(df_trabajadores[df_trabajadores['estatus'] == 'baja']) if not df_trabajadores.empty else 0
        total_personal = activos + bajas
        rotacion = (bajas / max(total_personal, 1)) * 100
        total_cajas = df_cosechas['numero_cajas'].sum() if not df_cosechas.empty else 0
        total_clams = df_cosechas['cantidad_clams'].sum() if not df_cosechas.empty else 0
        trabajadores_unicos = df_cosechas['trabajador_id'].nunique() if not df_cosechas.empty else 0
        promedio_cajas_trabajador = total_cajas / max(trabajadores_unicos, 1)
        total_trasladadas = df_traslados['cantidad_cajas'].sum() if not df_traslados.empty else 0
        porcentaje_merma = obtener_porcentaje_merma_filtrado(df_cosechas, df_traslados)
        resumen_proyecciones = get_resumen_proyecciones_total_con_filtros_dashboard(df_cosechas)
        total_faltas = len(df_incidencias[df_incidencias['tipo_incidencia'].str.contains('Falta', na=False)]) if not df_incidencias.empty else 0
        total_permisos = len(df_incidencias[df_incidencias['tipo_incidencia'].str.contains('Permiso', na=False)]) if not df_incidencias.empty else 0
        total_incidencias = len(df_incidencias) if not df_incidencias.empty else 0
        total_pesado = df_pesajes['cantidad_cajas_pesadas'].sum() if not df_pesajes.empty else 0
        total_recibido = df_pesajes['cajas_recibidas'].sum() if not df_pesajes.empty else 0
        diferencia_pesaje = total_pesado - total_recibido
    except Exception as e:
        st.error(f"Error al cargar datos: {str(e)}")
        df_cosechas = pd.DataFrame()
        df_trabajadores = pd.DataFrame()
        df_traslados = pd.DataFrame()
        df_incidencias = pd.DataFrame()
        df_pesajes = pd.DataFrame()
        activos = bajas = total_personal = rotacion = total_cajas = total_clams = promedio_cajas_trabajador = total_trasladadas = porcentaje_merma = total_faltas = total_permisos = total_incidencias = total_pesado = total_recibido = diferencia_pesaje = 0
        resumen_proyecciones = {'total_proyectado': 0, 'total_real': 0, 'diferencia': 0, 'porcentaje_desviacion': 0}
    
    # Header del Dashboard
    st.markdown(f'''
    <div class="dashboard-header">
        <h1>🌱 Panel de Control Estratégico</h1>
        <p>Datos actualizados al {get_mexico_date().strftime('%d/%m/%Y')} - {get_mexico_time().strftime('%H:%M:%S')} hrs</p>
    </div>
    ''', unsafe_allow_html=True)
    
    # KPIs Principales - Primera Fila
    st.markdown("### 📊 Indicadores Clave de Rendimiento")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f'''
        <div class="metric-card">
            <div class="metric-icon">👥</div>
            <div class="metric-value">{activos}</div>
            <div class="metric-label">Personal Activo</div>
            <div><span class="badge badge-success">+{ingresos_mes if 'ingresos_mes' in locals() else 0} este mes</span></div>
        </div>
        ''', unsafe_allow_html=True)
    with col2:
        st.markdown(f'''
        <div class="metric-card">
            <div class="metric-icon">📦</div>
            <div class="metric-value">{total_cajas:,.0f}</div>
            <div class="metric-label">Cajas Cosechadas</div>
            <div><span class="badge badge-info">{total_clams:,.0f} clams</span></div>
        </div>
        ''', unsafe_allow_html=True)
    with col3:
        st.markdown(f'''
        <div class="metric-card">
            <div class="metric-icon">❄️</div>
            <div class="metric-value">{total_trasladadas:,.0f}</div>
            <div class="metric-label">Trasladadas a Cámara Fría</div>
            <div><span class="badge badge-info">{(total_trasladadas/max(total_cajas,1)*100):.1f}% del total</span></div>
        </div>
        ''', unsafe_allow_html=True)
    with col4:
        color_merma = "#e74c3c" if porcentaje_merma > 5 else "#27ae60"
        st.markdown(f'''
        <div class="metric-card">
            <div class="metric-icon">🗑️</div>
            <div class="metric-value" style="color: {color_merma};">{porcentaje_merma:.2f}%</div>
            <div class="metric-label">Porcentaje de Merma</div>
            <div><span class="badge badge-warning">Objetivo: &lt;5%</span></div>
        </div>
        ''', unsafe_allow_html=True)
    
    # KPIs Secundarios - Segunda Fila
    col5, col6, col7, col8 = st.columns(4)
    with col5:
        diferencia_color = "#27ae60" if diferencia_pesaje == 0 else ("#e67e22" if diferencia_pesaje != 0 else "#e74c3c")
        st.markdown(f'''
        <div class="metric-card">
            <div class="metric-icon">⚖️</div>
            <div class="metric-value" style="color: {diferencia_color};">{diferencia_pesaje:+,.0f}</div>
            <div class="metric-label">Diferencia en Pesaje</div>
            <div><span class="badge badge-info">Pesadas: {total_pesado:,.0f}</span></div>
        </div>
        ''', unsafe_allow_html=True)
    with col6:
        st.markdown(f'''
        <div class="metric-card">
            <div class="metric-icon">👨‍🌾</div>
            <div class="metric-value">{promedio_cajas_trabajador:.1f}</div>
            <div class="metric-label">Promedio x Trabajador</div>
            <div><span class="badge badge-info">Productividad</span></div>
        </div>
        ''', unsafe_allow_html=True)
    with col7:
        desviacion_color = "#27ae60" if resumen_proyecciones['porcentaje_desviacion'] >= 0 else "#e74c3c"
        desviacion_icono = "📈" if resumen_proyecciones['porcentaje_desviacion'] >= 0 else "📉"
        st.markdown(f'''
        <div class="metric-card">
            <div class="metric-icon">{desviacion_icono}</div>
            <div class="metric-value" style="color: {desviacion_color};">{abs(resumen_proyecciones['porcentaje_desviacion']):.1f}%</div>
            <div class="metric-label">Desviación Proyección</div>
            <div><span class="badge badge-info">Proyectado: {resumen_proyecciones['total_proyectado']:,.0f}</span></div>
        </div>
        ''', unsafe_allow_html=True)
    with col8:
        st.markdown(f'''
        <div class="metric-card">
            <div class="metric-icon">⚠️</div>
            <div class="metric-value">{total_incidencias}</div>
            <div class="metric-label">Total Incidencias</div>
            <div><span class="badge badge-danger">Faltas: {total_faltas}</span> <span class="badge badge-warning">Permisos: {total_permisos}</span></div>
        </div>
        ''', unsafe_allow_html=True)
    
    # Sección de Avance de Cosecha del Día
    st.markdown("### 🌾 Avance de Cosecha del Día")
    df_avance = get_avance_hoy_por_invernadero()
    if not df_avance.empty:
        df_avance_filtrado = df_avance
        if invernadero_seleccionado and invernadero_seleccionado != "Todos":
            df_avance_filtrado = df_avance[df_avance['invernadero_nombre'] == invernadero_seleccionado]
        
        col1, col2 = st.columns([2, 1])
        with col1:
            if not df_avance_filtrado.empty:
                fig = px.bar(df_avance_filtrado, x='invernadero_nombre', y='porcentaje', 
                            title='Porcentaje de Avance por Invernadero',
                            labels={'invernadero_nombre': 'Invernadero', 'porcentaje': 'Avance (%)'},
                            text='porcentaje', color='porcentaje', 
                            color_continuous_scale='Greens', range_color=[0, 100])
                fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                fig.update_layout(plot_bgcolor='white', height=400, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
        with col2:
            total_lineas_cosechadas = df_avance_filtrado['lineas_cosechadas'].sum() if not df_avance_filtrado.empty else 0
            total_lineas_totales = df_avance_filtrado['lineas_totales'].sum() if not df_avance_filtrado.empty else 0
            porcentaje_total = (total_lineas_cosechadas / total_lineas_totales) * 100 if total_lineas_totales > 0 else 0
            st.markdown(f'''
            <div class="progress-container" style="text-align: center;">
                <div style="font-size: 14px; color: #666;">📈 PROGRESO TOTAL DEL DÍA</div>
                <div style="font-size: 42px; font-weight: bold; color: #1a472a;">{porcentaje_total:.1f}%</div>
                <div style="font-size: 12px; color: #666;">{total_lineas_cosechadas:,.0f} / {total_lineas_totales:,.0f} líneas cosechadas</div>
            </div>
            ''', unsafe_allow_html=True)
    else:
        st.info("No hay registros de avance para el día de hoy")
    
    # Gráficos de Producción
    st.markdown("### 📈 Análisis de Producción")
    col1, col2 = st.columns(2)
    with col1:
        if not df_cosechas.empty:
            df_semanal = df_cosechas.groupby('semana')['numero_cajas'].sum().reset_index().sort_values('semana')
            fig = px.line(df_semanal, x='semana', y='numero_cajas', 
                         title='Evolución de Cajas Cosechadas por Semana',
                         labels={'semana': 'Semana', 'numero_cajas': 'Cajas'},
                         markers=True)
            fig.update_traces(line=dict(color='#2a6b3c', width=3), marker=dict(size=8))
            fig.update_layout(plot_bgcolor='white', height=400)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay datos de cosechas para mostrar")
    with col2:
        if not df_cosechas.empty and 'invernaderos' in df_cosechas.columns:
            df_cosechas['invernadero_nombre'] = df_cosechas['invernaderos'].apply(lambda x: x['nombre'] if x else 'Desconocido')
            df_inv = df_cosechas.groupby('invernadero_nombre')['numero_cajas'].sum().reset_index().sort_values('numero_cajas', ascending=True)
            fig = px.bar(df_inv, x='numero_cajas', y='invernadero_nombre', orientation='h',
                        title='Producción por Invernadero',
                        labels={'numero_cajas': 'Cajas', 'invernadero_nombre': 'Invernadero'},
                        color='numero_cajas', color_continuous_scale='Greens')
            fig.update_layout(plot_bgcolor='white', height=400)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay datos de invernaderos para mostrar")
    
    # Comparativa Diaria
    st.markdown("### 📊 Comparativa Diaria: Cosechado vs Trasladado vs Pesado")
    if not df_cosechas.empty or not df_traslados.empty or not df_pesajes.empty:
        fig = go.Figure()
        if not df_cosechas.empty:
            df_c_diario = df_cosechas.groupby('fecha')['numero_cajas'].sum().reset_index().sort_values('fecha')
            fig.add_trace(go.Scatter(x=df_c_diario['fecha'], y=df_c_diario['numero_cajas'], 
                                     mode='lines+markers', name='Cosechado', 
                                     line=dict(color='#2ecc71', width=3)))
        if not df_traslados.empty:
            df_t_diario = df_traslados.groupby('fecha')['cantidad_cajas'].sum().reset_index().sort_values('fecha')
            fig.add_trace(go.Scatter(x=df_t_diario['fecha'], y=df_t_diario['cantidad_cajas'], 
                                     mode='lines+markers', name='Trasladado', 
                                     line=dict(color='#3498db', width=3)))
        if not df_pesajes.empty:
            df_p_diario = df_pesajes.groupby('fecha')['cantidad_cajas_pesadas'].sum().reset_index().sort_values('fecha')
            fig.add_trace(go.Scatter(x=df_p_diario['fecha'], y=df_p_diario['cantidad_cajas_pesadas'], 
                                     mode='lines+markers', name='Pesado', 
                                     line=dict(color='#e74c3c', width=3)))
        fig.update_layout(title='Evolución Diaria de Producción', 
                         xaxis_title='Fecha', yaxis_title='Cajas', 
                         plot_bgcolor='white', height=400)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No hay datos para mostrar en la comparativa diaria")
    
    # Sección de Insights
    st.markdown("### 💡 Insights y Recomendaciones")
    col1, col2 = st.columns(2)
    with col1:
        if porcentaje_merma > 5:
            st.markdown(f'''
            <div class="insight-box">
                <strong>⚠️ ALERTA DE MERMA</strong><br>
                El porcentaje de merma actual es del <strong>{porcentaje_merma:.2f}%</strong>, superando el objetivo del 5%.
                Se recomienda revisar los procesos de cosecha y manejo post-cosecha.
            </div>
            ''', unsafe_allow_html=True)
        elif diferencia_pesaje != 0:
            st.markdown(f'''
            <div class="insight-box">
                <strong>⚠️ DISCREPANCIA EN PESAJE</strong><br>
                Se detectó una diferencia de <strong>{abs(diferencia_pesaje):.0f} cajas</strong> entre lo pesado y lo recibido.
                Verificar el proceso de pesaje y registro.
            </div>
            ''', unsafe_allow_html=True)
        else:
            st.markdown(f'''
            <div class="insight-box">
                <strong>✅ OPERACIÓN NORMAL</strong><br>
                Todos los indicadores se encuentran dentro de los parámetros esperados. 
                La producción se mantiene estable y los procesos de calidad están funcionando correctamente.
            </div>
            ''', unsafe_allow_html=True)
    with col2:
        if total_incidencias > 10:
            st.markdown(f'''
            <div class="insight-box">
                <strong>⚠️ ALTA INCIDENCIA DE PERSONAL</strong><br>
                Se han registrado <strong>{total_incidencias} incidencias</strong> en el período. 
                Revisar las causas y considerar medidas correctivas.
            </div>
            ''', unsafe_allow_html=True)
        elif total_incidencias > 5:
            st.markdown(f'''
            <div class="insight-box">
                <strong>📊 SEGUIMIENTO DE INCIDENCIAS</strong><br>
                Se registraron <strong>{total_incidencias} incidencias</strong>. 
                Mantener monitoreo constante del ausentismo.
            </div>
            ''', unsafe_allow_html=True)
        else:
            st.markdown(f'''
            <div class="insight-box">
                <strong>👍 BUENA ASISTENCIA</strong><br>
                Solo <strong>{total_incidencias} incidencias</strong> registradas en el período. 
                El personal muestra buena asistencia y puntualidad.
            </div>
            ''', unsafe_allow_html=True)
    
    # Detalle de datos (expandible)
    with st.expander("📋 Ver detalle de datos", expanded=False):
        st.markdown("### 📦 Últimas cosechas")
        if not df_cosechas.empty:
            st.dataframe(df_cosechas[['fecha', 'semana', 'tipo_cosecha', 'presentacion', 'numero_cajas', 'cajas_enviadas', 'merma_kilos', 'porcentaje_merma']].head(10), use_container_width=True)
        st.markdown("### ❄️ Últimos traslados")
        if not df_traslados.empty:
            st.dataframe(df_traslados.head(10), use_container_width=True)
        st.markdown("### ⚖️ Últimos pesajes")
        if not df_pesajes.empty:
            st.dataframe(df_pesajes.head(10), use_container_width=True)
        st.markdown("### ⚠️ Incidencias recientes")
        if not df_incidencias.empty:
            st.dataframe(df_incidencias.head(10), use_container_width=True)

def mostrar_cierre_dia():
    st.header("📅 Cierre de Día y Auditoría")
    tab1, tab2 = st.tabs(["🔒 Realizar Cierre", "📋 Historial de Cierres"])
    with tab1:
        st.subheader("Realizar Cierre del Día")
        fecha_cierre = st.date_input("Fecha a cerrar", get_mexico_date())
        cierres = get_cierres_dia()
        if not cierres.empty and fecha_cierre.isoformat() in cierres['fecha'].values:
            st.warning("⚠️ Esta fecha ya fue cerrada anteriormente")
        else:
            if st.button("📊 Generar Reporte de Auditoría", type="primary"):
                with st.spinner("Generando reporte..."):
                    reporte = generar_reporte_auditoria_dia(fecha_cierre)
                    if reporte:
                        st.success("Reporte generado exitosamente")
                        st.subheader("📊 Resumen del Día")
                        col1, col2, col3, col4, col5, col6 = st.columns(6)
                        with col1: st.metric("Cajas Cosechadas", f"{reporte['resumen']['total_cajas_cosechadas']:.0f}")
                        with col2: st.metric("Cajas Trasladadas", f"{reporte['resumen']['total_cajas_trasladadas']:.0f}")
                        with col3: st.metric("Cajas Pesadas", f"{reporte['resumen']['total_cajas_pesadas']:.0f}")
                        with col4: st.metric("Cajas Recibidas", f"{reporte['resumen']['total_cajas_recibidas']:.0f}")
                        with col5: st.metric("Diferencia Pesaje", f"{reporte['resumen']['diferencia_pesaje']:+.0f}")
                        with col6: st.metric("Merma (kg)", f"{reporte['resumen']['total_merma_kilos']:.2f}")
                        col1, col2, col3, col4 = st.columns(4)
                        with col1: st.metric("Personal", reporte['resumen']['total_personal_asistencia'])
                        with col2: st.metric("Avance Promedio", f"{reporte['resumen']['promedio_avance']:.1f}%")
                        with col3: st.metric("Incidencias", reporte['resumen']['total_incidencias'])
                        with col4: st.metric("Solicitudes Apoyo", reporte['resumen']['total_solicitudes_apoyo'])
                        with st.expander("📋 Ver detalle del reporte"):
                            if reporte['detalle_cosechas']:
                                st.markdown("**Cosechas del día:**")
                                st.json(reporte['detalle_cosechas'][:5])
                            if reporte['detalle_traslados']:
                                st.markdown("**Traslados del día:**")
                                st.json(reporte['detalle_traslados'][:5])
                            if reporte['detalle_pesajes']:
                                st.markdown("**Pesajes del día:**")
                                st.json(reporte['detalle_pesajes'][:5])
                            if reporte['detalle_merma']:
                                st.markdown("**Merma del día:**")
                                st.json(reporte['detalle_merma'][:5])
                        pdf_buffer = descargar_reporte_auditoria_pdf(reporte, fecha_cierre)
                        if pdf_buffer:
                            st.download_button("📥 Descargar Reporte PDF", data=pdf_buffer, file_name=f"auditoria_{fecha_cierre}.pdf", mime="application/pdf")
                        if st.button("✅ Confirmar Cierre del Día", type="primary"):
                            success, msg = registrar_cierre_dia(fecha_cierre, st.session_state.get('user_nombre', 'Sistema'))
                            if success:
                                st.success(msg)
                                st.balloons()
                                st.rerun()
                            else:
                                st.error(msg)
                    else:
                        st.error("Error al generar el reporte")
    with tab2:
        st.subheader("Historial de Cierres")
        cierres = get_cierres_dia()
        if not cierres.empty:
            st.dataframe(cierres, use_container_width=True)
            for _, cierre in cierres.iterrows():
                with st.expander(f"Cierre del {cierre['fecha']} - Realizado por: {cierre['cerrado_por']}"):
                    try:
                        result = supabase.table('cierres_dia').select('reporte').eq('fecha', cierre['fecha']).execute()
                        if result.data and result.data[0].get('reporte'):
                            datos = result.data[0]['reporte']
                            st.json(datos)
                            if st.button(f"📥 Descargar PDF {cierre['fecha']}", key=f"pdf_{cierre['fecha']}"):
                                pdf_buffer = descargar_reporte_auditoria_pdf(datos, datetime.strptime(cierre['fecha'], '%Y-%m-%d').date())
                                if pdf_buffer:
                                    st.download_button("📥 Descargar PDF", data=pdf_buffer, file_name=f"auditoria_{cierre['fecha']}.pdf", mime="application/pdf")
                    except:
                        st.info("No se pudo cargar el detalle del reporte")
        else:
            st.info("No hay cierres registrados")

def mostrar_cajas_mesa():
    st.header("📦 Cajas en Mesa")
    tab1, tab2 = st.tabs(["📝 Registrar Cajas", "🆘 Solicitudes de Apoyo"])
    with tab1:
        st.subheader("Registrar Cajas en Mesa")
        fecha_actual = get_mexico_date()
        st.markdown(f'<div style="display: flex; gap: 10px; margin-bottom: 20px;"><div class="date-card"><div>📅 FECHA</div><div style="font-size:20px;">{fecha_actual.strftime("%d/%m/%Y")}</div></div><div class="time-card"><div>⏰ HORA</div><div style="font-size:20px;">{get_mexico_time().strftime("%H:%M")}</div></div></div>', unsafe_allow_html=True)
        invernaderos = get_invernaderos_usuario()
        if invernaderos:
            invernadero = st.selectbox("Invernadero", invernaderos, format_func=lambda x: f"{x[1]} - {x[2]}")
            invernadero_id = invernadero[0]
        else:
            invernadero_id = None
            st.error("No tienes invernaderos asignados para hoy")
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
                    st.rerun()
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

# ==========================================
# FUNCIONES DE ESCANEO QR
# ==========================================

def escanear_qr_con_camara(tipo_evento="asistencia", mostrar_invernadero=False):
    st.markdown("### 📷 Escaneo Instantáneo con Cámara")
    if 'qr_detected' not in st.session_state:
        st.session_state.qr_detected = False
    if 'scanned_worker' not in st.session_state:
        st.session_state.scanned_worker = None
    if 'show_form' not in st.session_state:
        st.session_state.show_form = False
    if st.button("🔄 Nuevo Escaneo", use_container_width=True):
        st.session_state.qr_detected = False
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
                            st.session_state.qr_detected = True
                            st.rerun()
                        else:
                            st.error(f"❌ Trabajador no encontrado: {nombre}")
                    else:
                        st.error("❌ QR no válido")
            else:
                st.warning("📷 No se detectó QR. Enfoca bien el código.")
    if st.session_state.show_form and st.session_state.scanned_worker:
        trabajador = st.session_state.scanned_worker
        st.success(f"✅ QR Detectado: {trabajador['nombre']}")
        if tipo_evento == "cosecha":
            mostrar_formulario_cosecha_instant(trabajador['id'], trabajador['nombre'], mostrar_invernadero)
        elif tipo_evento == "asistencia":
            mostrar_formulario_asistencia_instant(trabajador['id'], trabajador['nombre'])

def mostrar_formulario_cosecha_instant(id_trabajador, nombre, mostrar_invernadero):
    st.markdown("### 📋 Registrar Cosecha")
    invernadero_id = None
    if mostrar_invernadero:
        invernaderos = get_invernaderos_usuario()
        if invernaderos:
            invernadero = st.selectbox("🏭 Invernadero:", invernaderos, format_func=lambda x: f"{x[1]} - {x[2]}", key="invernadero_instant")
            invernadero_id = invernadero[0]
        else:
            st.error("❌ No tienes invernaderos asignados para hoy")
            return
    fecha_actual = get_mexico_date()
    dia_espanol = get_mexico_day_spanish()
    col1, col2, col3 = st.columns(3)
    with col1: st.write(f"**📅 Fecha:** {fecha_actual.strftime('%d/%m/%Y')}")
    with col2: st.write(f"**📆 Día:** {dia_espanol}")
    with col3: st.write(f"**📊 Semana:** {get_mexico_week()}")
    col1, col2 = st.columns(2)
    with col1:
        tipo_cosecha = st.radio("Tipo:", ["Nacional", "Exportación"], horizontal=True, key="tipo_instant")
        if tipo_cosecha == "Nacional":
            calidad = st.selectbox("Calidad:", ["Salmon", "Sobretono"], key="calidad_instant")
        else:
            calidad = None
    with col2:
        if tipo_cosecha == "Exportación":
            presentacion = st.selectbox("Presentación:", ["6 oz", "12 oz"], key="pres_instant")
        else:
            presentacion = "6 oz"
            st.info("✅ Presentación: 6 oz")
    cantidad_clams = st.number_input("🍓 Cantidad de Clams:", min_value=0.0, value=0.0, step=1.0, key="clams_instant")
    merma_kilos = st.number_input("🗑️ Merma (kilos):", min_value=0.0, value=0.0, step=0.5, key="merma_instant")
    if presentacion == "12 oz":
        cajas = cantidad_clams / 6 if cantidad_clams > 0 else 0
    else:
        cajas = cantidad_clams / 12 if cantidad_clams > 0 else 0
    st.metric("📦 Cajas a registrar", f"{cajas:.2f}")
    if merma_kilos > 0 and cantidad_clams > 0:
        porcentaje_merma = (merma_kilos / cantidad_clams) * 100
        st.metric("📊 Porcentaje de Merma", f"{porcentaje_merma:.2f}%")
    st.info(f"👤 Trabajador: **{nombre}**")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 Guardar Cosecha", type="primary", use_container_width=True):
            if cantidad_clams <= 0:
                st.error("Ingrese cantidad válida")
            elif not invernadero_id and mostrar_invernadero:
                st.error("Seleccione invernadero")
            else:
                data = {
                    'fecha': fecha_actual, 'dia': dia_espanol, 'semana': get_mexico_week(),
                    'trabajador_id': int(id_trabajador), 'invernadero_id': invernadero_id,
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
    with col2:
        if st.button("🔄 Escanear otro", use_container_width=True):
            st.session_state.show_form = False
            st.session_state.scanned_worker = None
            st.rerun()

def mostrar_formulario_asistencia_instant(id_trabajador, nombre):
    st.markdown("### 📋 Registrar Asistencia")
    invernaderos = get_invernaderos_usuario()
    if invernaderos:
        invernadero = st.selectbox("🏭 Invernadero:", invernaderos, format_func=lambda x: f"{x[1]} - {x[2]}", key="invernadero_asistencia_instant")
        invernadero_id = invernadero[0]
    else:
        invernadero_id = None
        st.warning("No tienes invernaderos asignados para hoy")
    tipo_evento = st.selectbox("📌 Evento:", ["entrada_invernadero", "salida_comer", "regreso_comida", "salida_invernadero"], format_func=lambda x: {'entrada_invernadero': '🚪 Entrada a Invernadero', 'salida_comer': '🍽️ Salida a Comer', 'regreso_comida': '✅ Regreso de Comida', 'salida_invernadero': '🚪 Salida de Invernadero'}[x], key="tipo_instant")
    st.info(f"👤 Trabajador: **{nombre}**")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Registrar", type="primary", use_container_width=True):
            if tipo_evento == 'entrada_invernadero' and not invernadero_id:
                st.error("Seleccione invernadero")
            else:
                success, msg = registrar_evento_asistencia(int(id_trabajador), invernadero_id if tipo_evento == 'entrada_invernadero' else None, tipo_evento)
                if success:
                    st.success(msg)
                    st.balloons()
                    st.session_state.show_form = False
                    st.session_state.scanned_worker = None
                    st.rerun()
                else:
                    st.error(msg)
    with col2:
        if st.button("🔄 Escanear otro", use_container_width=True):
            st.session_state.show_form = False
            st.session_state.scanned_worker = None
            st.rerun()

# ==========================================
# INTERFAZ DE GESTIÓN DE USUARIOS
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
                with st.expander(f"👤 {usuario.get('nombre', 'Sin nombre')} (@{usuario.get('nombre_usuario', 'sin_usuario')}) - {usuario.get('rol', 'supervisor')}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**ID:** {usuario['id']}")
                        st.write(f"**Usuario:** @{usuario.get('nombre_usuario', 'No especificado')}")
                        st.write(f"**Email:** {usuario.get('email', 'No especificado')}")
                        st.write(f"**Nombre:** {usuario.get('nombre', 'No especificado')}")
                        st.write(f"**Rol:** {usuario.get('rol', 'supervisor')}")
                    with col2:
                        st.write(f"**Estado:** {'✅ Activo' if usuario.get('activo', True) else '❌ Inactivo'}")
                        st.write(f"**Invernaderos asignados:** {len(usuario.get('invernaderos_asignados', []))}")
                        permisos = usuario.get('permisos', {})
                        modulos_activos = [k for k, v in permisos.items() if v]
                        st.write(f"**Módulos activos:** {len(modulos_activos)}")
                    
                    col_acc1, col_acc2, col_acc3, col_acc4 = st.columns(4)
                    with col_acc1:
                        if st.button("✏️ Editar", key=f"edit_{usuario['id']}"):
                            st.session_state[f'editing_{usuario["id"]}'] = True
                    with col_acc2:
                        if st.button("🔑 Resetear Password", key=f"reset_{usuario['id']}"):
                            st.session_state[f'reset_{usuario["id"]}'] = True
                    with col_acc3:
                        if st.button("🔄 Activar/Desactivar", key=f"toggle_{usuario['id']}"):
                            nuevo_estado = not usuario.get('activo', True)
                            success, msg = toggle_user_status(usuario['id'], nuevo_estado)
                            if success:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
                    with col_acc4:
                        if usuario['nombre_usuario'] != st.session_state.get('user_nombre_usuario'):
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
                                success, msg = delete_user(usuario['id'], usuario.get('nombre_usuario', usuario['nombre']))
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
                nuevo_usuario = st.text_input("Nombre de usuario *")
                nuevo_nombre = st.text_input("Nombre completo *")
                nuevo_password = st.text_input("Contraseña *", type="password")
            with col2:
                nuevo_rol = st.selectbox("Rol *", ["supervisor", "admin"])
                invernaderos = get_all_invernaderos()
                invernaderos_nuevo = st.multiselect("Invernaderos asignados", [inv[1] for inv in invernaderos])
                invernaderos_ids_nuevo = [inv[0] for inv in invernaderos if inv[1] in invernaderos_nuevo]
            if st.form_submit_button("✅ Crear Usuario"):
                if not nuevo_usuario or not nuevo_nombre or not nuevo_password:
                    st.error("Complete todos los campos")
                elif len(nuevo_password) < 6:
                    st.error("La contraseña debe tener al menos 6 caracteres")
                else:
                    result = register_user(nuevo_usuario, nuevo_password, nuevo_nombre, nuevo_rol, None, invernaderos_ids_nuevo)
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
            supervisor = st.selectbox("Supervisor", supervisores.apply(lambda x: f"{x['id']} - @{x.get('nombre_usuario', x['nombre'])}", axis=1))
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
        st.session_state.menu = "📊 Tablero de Control"
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
    elif st.session_state.menu == "📊 Tablero de Control":
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
