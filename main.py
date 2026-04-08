import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
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

# ==========================================
# CONFIGURACIÓN INICIAL
# ==========================================

st.set_page_config(
    page_title="Sistema Integral de Gestión",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilo personalizado para el sidebar
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
    </style>
""", unsafe_allow_html=True)

# ==========================================
# CONFIGURACIÓN BASE DE DATOS LOCAL
# ==========================================

DB_PATH = "sistema_gestion.db"

def migrar_base_datos():
    """Función para migrar la base de datos existente agregando columnas faltantes"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 1. Verificar y agregar columna tipo_evento a registros_asistencia
        try:
            cursor.execute("PRAGMA table_info(registros_asistencia)")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            if 'tipo_evento' not in column_names:
                cursor.execute("ALTER TABLE registros_asistencia ADD COLUMN tipo_evento TEXT")
                cursor.execute("UPDATE registros_asistencia SET tipo_evento = 'entrada_invernadero' WHERE tipo_evento IS NULL")
        except Exception:
            pass
        
        # 2. Verificar y agregar columnas a envios_enfriado
        try:
            cursor.execute("PRAGMA table_info(envios_enfriado)")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            if 'tipo_envio' not in column_names:
                cursor.execute("ALTER TABLE envios_enfriado ADD COLUMN tipo_envio TEXT DEFAULT 'Nacional'")
            
            if 'hora' not in column_names:
                cursor.execute("ALTER TABLE envios_enfriado ADD COLUMN hora TIME")
            
            if 'presentacion' not in column_names:
                cursor.execute("ALTER TABLE envios_enfriado ADD COLUMN presentacion TEXT DEFAULT '6 oz'")
            
            if 'lote' not in column_names:
                cursor.execute("ALTER TABLE envios_enfriado ADD COLUMN lote TEXT")
            
            if 'trabajador_envia_id' not in column_names:
                cursor.execute("ALTER TABLE envios_enfriado ADD COLUMN trabajador_envia_id INTEGER")
                cursor.execute("UPDATE envios_enfriado SET trabajador_envia_id = trabajador_id WHERE trabajador_envia_id IS NULL")
            
            if 'trabajador_recibe_id' not in column_names:
                cursor.execute("ALTER TABLE envios_enfriado ADD COLUMN trabajador_recibe_id INTEGER")
                cursor.execute("UPDATE envios_enfriado SET trabajador_recibe_id = trabajador_id WHERE trabajador_recibe_id IS NULL")
                
        except Exception:
            pass
        
        # 3. Verificar y agregar columna cajas_enviadas a cosechas
        try:
            cursor.execute("PRAGMA table_info(cosechas)")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            if 'cajas_enviadas' not in column_names:
                cursor.execute("ALTER TABLE cosechas ADD COLUMN cajas_enviadas REAL DEFAULT 0")
        except Exception:
            pass
        
        conn.commit()
        conn.close()
    except Exception:
        pass

def init_database():
    """Inicializa la base de datos SQLite con todas las tablas necesarias"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Tabla de departamentos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS departamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE NOT NULL
        )
    ''')
    
    # Tabla de subdepartamentos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subdepartamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE NOT NULL
        )
    ''')
    
    # Tabla de puestos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS puestos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE NOT NULL
        )
    ''')
    
    # Tabla de trabajadores
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trabajadores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            apellido_paterno TEXT NOT NULL,
            apellido_materno TEXT,
            nombre TEXT NOT NULL,
            correo TEXT,
            telefono TEXT,
            fecha_alta DATE NOT NULL,
            fecha_baja DATE,
            estatus TEXT DEFAULT 'activo',
            departamento_id INTEGER,
            subdepartamento_id INTEGER,
            tipo_nomina TEXT,
            puesto_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (departamento_id) REFERENCES departamentos(id),
            FOREIGN KEY (subdepartamento_id) REFERENCES subdepartamentos(id),
            FOREIGN KEY (puesto_id) REFERENCES puestos(id)
        )
    ''')
    
    # Tabla de cosechas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cosechas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha DATE NOT NULL,
            dia TEXT NOT NULL,
            semana INTEGER NOT NULL,
            trabajador_id INTEGER,
            modulo INTEGER NOT NULL,
            tipo_cosecha TEXT NOT NULL,
            calidad TEXT,
            presentacion TEXT NOT NULL,
            cantidad_clams REAL NOT NULL,
            numero_cajas REAL NOT NULL,
            cajas_enviadas REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (trabajador_id) REFERENCES trabajadores(id)
        )
    ''')
    
    # Tabla de invernaderos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS invernaderos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE NOT NULL,
            ubicacion TEXT,
            activo BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabla de control de asistencia
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS asistencia (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trabajador_id INTEGER NOT NULL,
            invernadero_id INTEGER,
            fecha DATE NOT NULL,
            hora_entrada TIME,
            hora_salida TIME,
            hora_entrada_comida TIME,
            hora_salida_comida TIME,
            tipo_movimiento TEXT,
            estado TEXT DEFAULT 'activo',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (trabajador_id) REFERENCES trabajadores(id),
            FOREIGN KEY (invernadero_id) REFERENCES invernaderos(id)
        )
    ''')
    
    # Tabla de registros detallados
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS registros_asistencia (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trabajador_id INTEGER NOT NULL,
            invernadero_id INTEGER,
            fecha DATE NOT NULL,
            hora TIME NOT NULL,
            tipo_evento TEXT NOT NULL,
            observaciones TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (trabajador_id) REFERENCES trabajadores(id),
            FOREIGN KEY (invernadero_id) REFERENCES invernaderos(id)
        )
    ''')
    
    # Tabla de descansos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS descansos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trabajador_id INTEGER NOT NULL,
            fecha DATE NOT NULL,
            tipo_descanso TEXT NOT NULL,
            observaciones TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (trabajador_id) REFERENCES trabajadores(id),
            UNIQUE(trabajador_id, fecha)
        )
    ''')
    
    # Tabla de envíos a enfriado - VERSIÓN CORREGIDA
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS envios_enfriado (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha DATE NOT NULL,
            hora TIME,
            invernadero_id INTEGER NOT NULL,
            trabajador_envia_id INTEGER,
            trabajador_recibe_id INTEGER,
            trabajador_id INTEGER,
            tipo_envio TEXT DEFAULT 'Nacional',
            presentacion TEXT DEFAULT '6 oz',
            cantidad_cajas REAL NOT NULL,
            lote TEXT,
            observaciones TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (invernadero_id) REFERENCES invernaderos(id),
            FOREIGN KEY (trabajador_envia_id) REFERENCES trabajadores(id),
            FOREIGN KEY (trabajador_recibe_id) REFERENCES trabajadores(id),
            FOREIGN KEY (trabajador_id) REFERENCES trabajadores(id)
        )
    ''')
    
    # Insertar datos de ejemplo
    cursor.execute("SELECT COUNT(*) FROM departamentos")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT INTO departamentos (nombre) VALUES (?)", 
                          [("Producción",), ("Empaque",), ("Calidad",), ("Logística",)])
    
    cursor.execute("SELECT COUNT(*) FROM subdepartamentos")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT INTO subdepartamentos (nombre) VALUES (?)",
                          [("Cosecha",), ("Postcosecha",), ("Control Calidad",), ("Almacén",)])
    
    cursor.execute("SELECT COUNT(*) FROM puestos")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT INTO puestos (nombre) VALUES (?)",
                          [("Operario",), ("Supervisor",), ("Jefe de Cuadrilla",), 
                           ("Técnico",), ("Control de Calidad",)])
    
    cursor.execute("SELECT COUNT(*) FROM invernaderos")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT INTO invernaderos (nombre, ubicacion) VALUES (?, ?)",
                          [("Invernadero Norte", "Zona Norte"), ("Invernadero Sur", "Zona Sur"),
                           ("Invernadero Este", "Zona Este"), ("Invernadero Oeste", "Zona Oeste"),
                           ("Invernadero Central", "Zona Central")])
    
    # Crear índices
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cosechas_fecha ON cosechas(fecha)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trabajadores_estatus ON trabajadores(estatus)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_asistencia_fecha ON asistencia(fecha)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_registros_fecha ON registros_asistencia(fecha)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_envios_fecha ON envios_enfriado(fecha)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_descansos_fecha ON descansos(fecha)")
        
        cursor.execute("PRAGMA table_info(registros_asistencia)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        if 'tipo_evento' in column_names:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_registros_tipo ON registros_asistencia(tipo_evento)")
    except Exception:
        pass
    
    conn.commit()
    conn.close()

# Inicializar y migrar base de datos
init_database()
migrar_base_datos()

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
# FUNCIONES PARA CATÁLOGOS
# ==========================================

def get_departamentos():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT id, nombre FROM departamentos ORDER BY nombre", conn)
    conn.close()
    return [(row['id'], row['nombre']) for _, row in df.iterrows()]

def get_subdepartamentos():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT id, nombre FROM subdepartamentos ORDER BY nombre", conn)
    conn.close()
    return [(row['id'], row['nombre']) for _, row in df.iterrows()]

def get_puestos():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT id, nombre FROM puestos ORDER BY nombre", conn)
    conn.close()
    return [(row['id'], row['nombre']) for _, row in df.iterrows()]

def get_departamentos_nombres():
    return [nombre for _, nombre in get_departamentos()]

def get_subdepartamentos_nombres():
    return [nombre for _, nombre in get_subdepartamentos()]

def get_puestos_nombres():
    return [nombre for _, nombre in get_puestos()]

def add_catalog_item(tabla, nombre):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(f"INSERT INTO {tabla} (nombre) VALUES (?)", (nombre.lower().strip(),))
        conn.commit()
        conn.close()
        return True, "✅ Item agregado correctamente"
    except sqlite3.IntegrityError:
        return False, "❌ Este nombre ya existe"
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

def update_catalog_item(tabla, item_id, nuevo_nombre):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(f"UPDATE {tabla} SET nombre = ? WHERE id = ?", (nuevo_nombre.lower().strip(), item_id))
        conn.commit()
        conn.close()
        return True, "✅ Item actualizado correctamente"
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

def delete_catalog_item(tabla, item_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute(f"SELECT id FROM {tabla} WHERE id = ?", (item_id,))
        if not cursor.fetchone():
            conn.close()
            return False, f"❌ El item no existe"
        
        if tabla == "departamentos":
            cursor.execute("SELECT COUNT(*) FROM trabajadores WHERE departamento_id = ?", (item_id,))
        elif tabla == "subdepartamentos":
            cursor.execute("SELECT COUNT(*) FROM trabajadores WHERE subdepartamento_id = ?", (item_id,))
        else:
            cursor.execute("SELECT COUNT(*) FROM trabajadores WHERE puesto_id = ?", (item_id,))
        
        count = cursor.fetchone()[0]
        if count > 0:
            conn.close()
            return False, f"❌ No se puede eliminar: {count} trabajadores lo están usando"
        
        cursor.execute(f"DELETE FROM {tabla} WHERE id = ?", (item_id,))
        conn.commit()
        conn.close()
        return True, "✅ Item eliminado correctamente"
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

# ==========================================
# FUNCIONES DE TRABAJADORES
# ==========================================

def get_id_by_nombre(tabla, nombre):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(f"SELECT id FROM {tabla} WHERE nombre = ?", (nombre,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def get_all_workers():
    conn = sqlite3.connect(DB_PATH)
    try:
        query = """
            SELECT t.id, t.nombre, t.apellido_paterno, t.apellido_materno,
                   t.correo, t.telefono, t.estatus, t.fecha_alta, t.fecha_baja,
                   COALESCE(d.nombre, 'Sin asignar') as departamento, 
                   COALESCE(s.nombre, 'Sin asignar') as subdepartamento,
                   COALESCE(p.nombre, 'Sin asignar') as puesto, 
                   t.tipo_nomina
            FROM trabajadores t
            LEFT JOIN departamentos d ON t.departamento_id = d.id
            LEFT JOIN subdepartamentos s ON t.subdepartamento_id = s.id
            LEFT JOIN puestos p ON t.puesto_id = p.id
            ORDER BY t.apellido_paterno, t.nombre
        """
        df = pd.read_sql_query(query, conn)
        return df
    except Exception as e:
        st.error(f"Error al obtener trabajadores: {str(e)}")
        return pd.DataFrame()
    finally:
        conn.close()

def get_worker_by_id(worker_id):
    conn = sqlite3.connect(DB_PATH)
    try:
        query = """
            SELECT t.*, 
                   COALESCE(d.nombre, '') as departamento_nombre,
                   COALESCE(s.nombre, '') as subdepartamento_nombre,
                   COALESCE(p.nombre, '') as puesto_nombre
            FROM trabajadores t
            LEFT JOIN departamentos d ON t.departamento_id = d.id
            LEFT JOIN subdepartamentos s ON t.subdepartamento_id = s.id
            LEFT JOIN puestos p ON t.puesto_id = p.id
            WHERE t.id = ?
        """
        df = pd.read_sql_query(query, conn, params=(worker_id,))
        if not df.empty:
            return df.iloc[0].to_dict()
        return None
    except Exception as e:
        st.error(f"Error al obtener trabajador: {str(e)}")
        return None
    finally:
        conn.close()

def add_worker(data):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        depto_id = get_id_by_nombre("departamentos", data['departamento'])
        sub_id = get_id_by_nombre("subdepartamentos", data['subdepartamento'])
        puesto_id = get_id_by_nombre("puestos", data['puesto'])
        
        cursor.execute("""
            INSERT INTO trabajadores
            (apellido_paterno, apellido_materno, nombre, correo, telefono,
             fecha_alta, estatus, departamento_id, subdepartamento_id,
             tipo_nomina, puesto_id)
            VALUES (?, ?, ?, ?, ?, ?, 'activo', ?, ?, ?, ?)
        """, (data['ap'], data['am'], data['nom'], data['cor'], data['tel'],
              data['fa'], depto_id, sub_id, data['tn'], puesto_id))
        
        conn.commit()
        conn.close()
        return True, "✅ Trabajador guardado correctamente"
    except Exception as e:
        return False, f"❌ Error al guardar: {str(e)}"

def update_worker(worker_id, data):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        depto_id = get_id_by_nombre("departamentos", data['departamento'])
        sub_id = get_id_by_nombre("subdepartamentos", data['subdepartamento'])
        puesto_id = get_id_by_nombre("puestos", data['puesto'])
        
        cursor.execute("""
            UPDATE trabajadores 
            SET apellido_paterno = ?,
                apellido_materno = ?,
                nombre = ?,
                correo = ?,
                telefono = ?,
                departamento_id = ?,
                subdepartamento_id = ?,
                tipo_nomina = ?,
                puesto_id = ?,
                estatus = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (data['apellido_paterno'], data['apellido_materno'], data['nombre'],
              data['correo'], data['telefono'], depto_id, sub_id, 
              data['tipo_nomina'], puesto_id, data['estatus'], worker_id))
        
        conn.commit()
        conn.close()
        return True, "✅ Cambios guardados correctamente"
    except Exception as e:
        return False, f"❌ Error al actualizar: {str(e)}"

def dar_baja(worker_id, fecha_baja):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE trabajadores 
            SET estatus = 'baja', 
                fecha_baja = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (fecha_baja, worker_id))
        conn.commit()
        conn.close()
        return True, "✅ Trabajador dado de baja correctamente"
    except Exception as e:
        return False, f"❌ Error al dar de baja: {str(e)}"

def reactivar_trabajador(worker_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE trabajadores 
            SET estatus = 'activo', 
                fecha_baja = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (worker_id,))
        conn.commit()
        conn.close()
        return True, "✅ Trabajador reactivado correctamente"
    except Exception as e:
        return False, f"❌ Error al reactivar: {str(e)}"

def search_workers(search_term, estatus_filter="todos"):
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT t.id, t.nombre, t.apellido_paterno, t.apellido_materno,
               t.correo, t.telefono, t.estatus, t.fecha_alta, t.fecha_baja,
               COALESCE(d.nombre, 'Sin asignar') as departamento, 
               COALESCE(s.nombre, 'Sin asignar') as subdepartamento,
               COALESCE(p.nombre, 'Sin asignar') as puesto, 
               t.tipo_nomina
        FROM trabajadores t
        LEFT JOIN departamentos d ON t.departamento_id = d.id
        LEFT JOIN subdepartamentos s ON t.subdepartamento_id = s.id
        LEFT JOIN puestos p ON t.puesto_id = p.id
        WHERE (LOWER(t.nombre) LIKE LOWER(?) 
           OR LOWER(t.apellido_paterno) LIKE LOWER(?)
           OR LOWER(t.apellido_materno) LIKE LOWER(?))
    """
    params = [f"%{search_term}%", f"%{search_term}%", f"%{search_term}%"]
    
    if estatus_filter != "todos":
        query += f" AND t.estatus = '{estatus_filter}'"
    
    query += " ORDER BY t.apellido_paterno, t.nombre"
    
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

# ==========================================
# FUNCIONES PARA INVERNADEROS
# ==========================================

def get_invernaderos():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT id, nombre, ubicacion FROM invernaderos WHERE activo = 1 ORDER BY nombre", conn)
    conn.close()
    return [(row['id'], row['nombre'], row['ubicacion']) for _, row in df.iterrows()]

def add_invernadero(nombre, ubicacion):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO invernaderos (nombre, ubicacion) VALUES (?, ?)", 
                      (nombre.strip().upper(), ubicacion))
        conn.commit()
        conn.close()
        return True, "✅ Invernadero agregado correctamente"
    except sqlite3.IntegrityError:
        return False, "❌ Este invernadero ya existe"
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

def update_invernadero(invernadero_id, nombre, ubicacion):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("UPDATE invernaderos SET nombre = ?, ubicacion = ? WHERE id = ?", 
                      (nombre.strip().upper(), ubicacion, invernadero_id))
        conn.commit()
        conn.close()
        return True, "✅ Invernadero actualizado correctamente"
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

def delete_invernadero(invernadero_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM asistencia WHERE invernadero_id = ?", (invernadero_id,))
        count = cursor.fetchone()[0]
        if count > 0:
            cursor.execute("UPDATE invernaderos SET activo = 0 WHERE id = ?", (invernadero_id,))
            conn.commit()
            conn.close()
            return True, "✅ Invernadero desactivado correctamente"
        
        cursor.execute("DELETE FROM invernaderos WHERE id = ?", (invernadero_id,))
        conn.commit()
        conn.close()
        return True, "✅ Invernadero eliminado correctamente"
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

# ==========================================
# FUNCIONES DE DESCANSO
# ==========================================

def registrar_descanso(trabajador_id, fecha, tipo_descanso, observaciones=""):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO descansos (trabajador_id, fecha, tipo_descanso, observaciones)
            VALUES (?, ?, ?, ?)
        """, (trabajador_id, fecha, tipo_descanso, observaciones))
        
        conn.commit()
        conn.close()
        return True, f"✅ Descanso registrado: {tipo_descanso}"
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

def get_descansos(fecha_inicio=None, fecha_fin=None):
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT d.*, 
               t.nombre || ' ' || t.apellido_paterno as trabajador
        FROM descansos d
        LEFT JOIN trabajadores t ON d.trabajador_id = t.id
        WHERE 1=1
    """
    params = []
    
    if fecha_inicio:
        query += " AND d.fecha >= ?"
        params.append(fecha_inicio)
    if fecha_fin:
        query += " AND d.fecha <= ?"
        params.append(fecha_fin)
    
    query += " ORDER BY d.fecha DESC"
    
    df = pd.read_sql_query(query, conn, params=params if params else None)
    conn.close()
    return df

# ==========================================
# FUNCIONES DE CONTROL DE ASISTENCIA
# ==========================================

def registrar_evento_asistencia(trabajador_id, invernadero_id, tipo_evento):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        fecha_actual = datetime.now().date()
        hora_actual = datetime.now().time()
        
        cursor.execute("""
            SELECT id, estado, hora_entrada, hora_salida_comida, hora_entrada_comida, hora_salida
            FROM asistencia 
            WHERE trabajador_id = ? AND fecha = ? AND estado != 'finalizado'
            ORDER BY id DESC LIMIT 1
        """, (trabajador_id, fecha_actual))
        
        registro_activo = cursor.fetchone()
        
        if tipo_evento == 'entrada_invernadero':
            if registro_activo:
                return False, "❌ Ya tienes un registro activo hoy"
            
            cursor.execute("""
                INSERT INTO asistencia 
                (trabajador_id, invernadero_id, fecha, hora_entrada, estado, tipo_movimiento)
                VALUES (?, ?, ?, ?, 'activo', ?)
            """, (trabajador_id, invernadero_id, fecha_actual, hora_actual, tipo_evento))
            
        elif tipo_evento == 'salida_comer':
            if not registro_activo:
                return False, "❌ No hay registro de entrada activo"
            if registro_activo[2] is None:
                return False, "❌ Primero debes registrar entrada"
            if registro_activo[3] is not None:
                return False, "❌ Ya registraste salida a comer"
            
            cursor.execute("""
                UPDATE asistencia 
                SET hora_salida_comida = ?, estado = 'comida', tipo_movimiento = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (hora_actual, tipo_evento, registro_activo[0]))
            
        elif tipo_evento == 'regreso_comida':
            if not registro_activo:
                return False, "❌ No hay registro de entrada activo"
            if registro_activo[3] is None:
                return False, "❌ Primero debes registrar salida a comer"
            if registro_activo[4] is not None:
                return False, "❌ Ya registraste regreso de comida"
            
            cursor.execute("""
                UPDATE asistencia 
                SET hora_entrada_comida = ?, estado = 'activo', tipo_movimiento = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (hora_actual, tipo_evento, registro_activo[0]))
            
        elif tipo_evento == 'salida_invernadero':
            if not registro_activo:
                return False, "❌ No hay registro de entrada activo"
            if registro_activo[2] is None:
                return False, "❌ Primero debes registrar entrada"
            if registro_activo[5] is not None:
                return False, "❌ Ya registraste salida"
            
            cursor.execute("""
                UPDATE asistencia 
                SET hora_salida = ?, estado = 'finalizado', tipo_movimiento = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (hora_actual, tipo_evento, registro_activo[0]))
        
        cursor.execute("""
            INSERT INTO registros_asistencia 
            (trabajador_id, invernadero_id, fecha, hora, tipo_evento, observaciones)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (trabajador_id, invernadero_id, fecha_actual, hora_actual, tipo_evento, 
              f"Registrado desde sistema"))
        
        conn.commit()
        conn.close()
        
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
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT a.id, a.estado, a.hora_entrada, a.hora_salida_comida, 
                   a.hora_entrada_comida, a.hora_salida, i.nombre as invernadero
            FROM asistencia a
            LEFT JOIN invernaderos i ON a.invernadero_id = i.id
            WHERE a.trabajador_id = ? AND a.fecha = ? AND a.estado != 'finalizado'
            ORDER BY a.id DESC LIMIT 1
        """, (trabajador_id, datetime.now().date()))
        
        registro = cursor.fetchone()
        conn.close()
        
        if registro:
            return {
                'id': registro[0],
                'estado': registro[1],
                'hora_entrada': registro[2],
                'hora_salida_comida': registro[3],
                'hora_entrada_comida': registro[4],
                'hora_salida': registro[5],
                'invernadero': registro[6]
            }
        return None
    except Exception as e:
        st.error(f"Error al obtener estado: {str(e)}")
        return None

def get_registros_asistencia(filtros=None):
    conn = sqlite3.connect(DB_PATH)
    
    query = """
        SELECT ra.id, 
               t.nombre || ' ' || t.apellido_paterno as trabajador,
               t.id as trabajador_id,
               i.nombre as invernadero,
               ra.fecha,
               ra.hora,
               ra.tipo_evento,
               ra.observaciones,
               ra.created_at
        FROM registros_asistencia ra
        LEFT JOIN trabajadores t ON ra.trabajador_id = t.id
        LEFT JOIN invernaderos i ON ra.invernadero_id = i.id
        WHERE 1=1
    """
    params = []
    
    if filtros:
        if filtros.get('trabajador_id'):
            query += " AND ra.trabajador_id = ?"
            params.append(filtros['trabajador_id'])
        
        if filtros.get('fecha_inicio'):
            query += " AND ra.fecha >= ?"
            params.append(filtros['fecha_inicio'])
        
        if filtros.get('fecha_fin'):
            query += " AND ra.fecha <= ?"
            params.append(filtros['fecha_fin'])
        
        if filtros.get('tipo_evento'):
            query += " AND ra.tipo_evento = ?"
            params.append(filtros['tipo_evento'])
    
    query += " ORDER BY ra.fecha DESC, ra.hora DESC"
    
    try:
        df = pd.read_sql_query(query, conn, params=params if params else None)
    except Exception:
        query_simple = """
            SELECT ra.id, 
                   t.nombre || ' ' || t.apellido_paterno as trabajador,
                   t.id as trabajador_id,
                   i.nombre as invernadero,
                   ra.fecha,
                   ra.hora,
                   '' as tipo_evento,
                   ra.observaciones,
                   ra.created_at
            FROM registros_asistencia ra
            LEFT JOIN trabajadores t ON ra.trabajador_id = t.id
            LEFT JOIN invernaderos i ON ra.invernadero_id = i.id
            WHERE 1=1
        """
        if filtros:
            if filtros.get('trabajador_id'):
                query_simple += " AND ra.trabajador_id = ?"
                params.append(filtros['trabajador_id'])
            
            if filtros.get('fecha_inicio'):
                query_simple += " AND ra.fecha >= ?"
                params.append(filtros['fecha_inicio'])
            
            if filtros.get('fecha_fin'):
                query_simple += " AND ra.fecha <= ?"
                params.append(filtros['fecha_fin'])
        
        query_simple += " ORDER BY ra.fecha DESC, ra.hora DESC"
        df = pd.read_sql_query(query_simple, conn, params=params if params else None)
    
    conn.close()
    return df

def get_resumen_asistencia_dia(fecha=None):
    if not fecha:
        fecha = datetime.now().date()
    
    conn = sqlite3.connect(DB_PATH)
    
    query = """
        SELECT 
            t.id,
            t.nombre || ' ' || t.apellido_paterno as trabajador,
            a.hora_entrada,
            a.hora_salida_comida,
            a.hora_entrada_comida,
            a.hora_salida,
            i.nombre as invernadero,
            a.estado,
            d.tipo_descanso as descanso,
            CASE 
                WHEN d.tipo_descanso IS NOT NULL THEN 'Descanso'
                WHEN a.hora_entrada IS NULL THEN 'Falta'
                WHEN a.hora_salida IS NULL THEN 'En invernadero'
                WHEN a.hora_salida_comida IS NOT NULL AND a.hora_entrada_comida IS NULL THEN 'En comida'
                ELSE 'Finalizado'
            END as estado_actual
        FROM trabajadores t
        LEFT JOIN asistencia a ON t.id = a.trabajador_id AND a.fecha = ?
        LEFT JOIN invernaderos i ON a.invernadero_id = i.id
        LEFT JOIN descansos d ON t.id = d.trabajador_id AND d.fecha = ?
        WHERE t.estatus = 'activo'
        ORDER BY t.apellido_paterno, t.nombre
    """
    
    df = pd.read_sql_query(query, conn, params=(fecha, fecha))
    conn.close()
    return df

def get_estadisticas_asistencia(fecha_inicio=None, fecha_fin=None):
    if not fecha_inicio:
        fecha_inicio = datetime.now().date() - timedelta(days=30)
    if not fecha_fin:
        fecha_fin = datetime.now().date()
    
    conn = sqlite3.connect(DB_PATH)
    
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(registros_asistencia)")
    columns = cursor.fetchall()
    column_names = [col[1] for col in columns]
    tiene_tipo_evento = 'tipo_evento' in column_names
    
    if tiene_tipo_evento:
        query_tipos = """
            SELECT tipo_evento, COUNT(*) as cantidad
            FROM registros_asistencia
            WHERE fecha BETWEEN ? AND ?
            GROUP BY tipo_evento
        """
        df_tipos = pd.read_sql_query(query_tipos, conn, params=(fecha_inicio, fecha_fin))
    else:
        df_tipos = pd.DataFrame(columns=['tipo_evento', 'cantidad'])
    
    # Consulta corregida para horas trabajadas
    query_horas = """
        SELECT 
            t.nombre || ' ' || t.apellido_paterno as trabajador,
            AVG(
                (strftime('%s', hora_salida) - strftime('%s', hora_entrada) - 
                 CASE 
                     WHEN hora_entrada_comida IS NOT NULL AND hora_salida_comida IS NOT NULL
                     THEN (strftime('%s', hora_entrada_comida) - strftime('%s', hora_salida_comida))
                     ELSE 0
                 END
                ) / 3600.0
            ) as horas_promedio
        FROM asistencia a
        LEFT JOIN trabajadores t ON a.trabajador_id = t.id
        WHERE a.fecha BETWEEN ? AND ? 
        AND a.hora_entrada IS NOT NULL 
        AND a.hora_salida IS NOT NULL
        GROUP BY a.trabajador_id
    """
    df_horas = pd.read_sql_query(query_horas, conn, params=(fecha_inicio, fecha_fin))
    
    query_tiempo_invernadero = """
        SELECT 
            i.nombre as invernadero,
            AVG(CAST((strftime('%s', hora_salida) - strftime('%s', hora_entrada)) / 3600.0 AS REAL)) as horas_promedio,
            COUNT(*) as visitas
        FROM asistencia a
        LEFT JOIN invernaderos i ON a.invernadero_id = i.id
        WHERE a.fecha BETWEEN ? AND ?
        AND a.hora_entrada IS NOT NULL 
        AND a.hora_salida IS NOT NULL
        GROUP BY i.nombre
    """
    df_tiempo_invernadero = pd.read_sql_query(query_tiempo_invernadero, conn, params=(fecha_inicio, fecha_fin))
    
    query_tiempo_comida = """
        SELECT 
            t.nombre || ' ' || t.apellido_paterno as trabajador,
            AVG(CAST((strftime('%s', hora_entrada_comida) - strftime('%s', hora_salida_comida)) / 3600.0 AS REAL)) as horas_comida
        FROM asistencia a
        LEFT JOIN trabajadores t ON a.trabajador_id = t.id
        WHERE a.fecha BETWEEN ? AND ?
        AND a.hora_salida_comida IS NOT NULL 
        AND a.hora_entrada_comida IS NOT NULL
        GROUP BY a.trabajador_id
    """
    df_tiempo_comida = pd.read_sql_query(query_tiempo_comida, conn, params=(fecha_inicio, fecha_fin))
    
    query_diaria = """
        SELECT 
            fecha,
            COUNT(DISTINCT trabajador_id) as total_trabajadores,
            COUNT(CASE WHEN hora_entrada IS NOT NULL THEN 1 END) as registraron_entrada,
            COUNT(CASE WHEN hora_salida IS NOT NULL THEN 1 END) as registraron_salida
        FROM asistencia
        WHERE fecha BETWEEN ? AND ?
        GROUP BY fecha
        ORDER BY fecha
    """
    df_diaria = pd.read_sql_query(query_diaria, conn, params=(fecha_inicio, fecha_fin))
    
    query_faltas = """
        SELECT 
            t.id,
            t.nombre || ' ' || t.apellido_paterno as trabajador,
            COUNT(CASE WHEN a.hora_entrada IS NULL AND d.tipo_descanso IS NULL THEN 1 END) as faltas,
            COUNT(CASE WHEN d.tipo_descanso IS NOT NULL THEN 1 END) as descansos
        FROM trabajadores t
        LEFT JOIN asistencia a ON t.id = a.trabajador_id AND a.fecha BETWEEN ? AND ?
        LEFT JOIN descansos d ON t.id = d.trabajador_id AND d.fecha BETWEEN ? AND ?
        WHERE t.estatus = 'activo'
        GROUP BY t.id
    """
    df_faltas = pd.read_sql_query(query_faltas, conn, params=(fecha_inicio, fecha_fin, fecha_inicio, fecha_fin))
    
    conn.close()
    
    return {
        'registros_por_tipo': df_tipos,
        'horas_promedio': df_horas,
        'tiempo_invernadero': df_tiempo_invernadero,
        'tiempo_comida': df_tiempo_comida,
        'asistencia_diaria': df_diaria,
        'faltas_descansos': df_faltas
    }

# ==========================================
# FUNCIONES DE COSECHA Y ENVÍOS
# ==========================================

def guardar_cosecha(data):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO cosechas
            (fecha, dia, semana, trabajador_id, modulo, tipo_cosecha,
             calidad, presentacion, cantidad_clams, numero_cajas)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (data['fecha'], data['dia'], data['semana'], data['trabajador_id'],
              data['modulo'], data['tipo_cosecha'], data['calidad'],
              data['presentacion'], data['cantidad_clams'], data['numero_cajas']))
        
        conn.commit()
        conn.close()
        return True, "✅ Cosecha registrada correctamente"
    except Exception as e:
        return False, f"❌ Error al guardar: {str(e)}"

def get_cosechas(fecha_inicio=None, fecha_fin=None):
    conn = sqlite3.connect(DB_PATH)
    
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(cosechas)")
    columns = cursor.fetchall()
    column_names = [col[1] for col in columns]
    tiene_cajas_enviadas = 'cajas_enviadas' in column_names
    
    if tiene_cajas_enviadas:
        query = """
            SELECT c.*, 
                   t.nombre || ' ' || t.apellido_paterno as trabajador_nombre,
                   (c.numero_cajas - c.cajas_enviadas) as cajas_disponibles
            FROM cosechas c
            LEFT JOIN trabajadores t ON c.trabajador_id = t.id
            WHERE 1=1
        """
    else:
        query = """
            SELECT c.*, 
                   t.nombre || ' ' || t.apellido_paterno as trabajador_nombre,
                   c.numero_cajas as cajas_disponibles
            FROM cosechas c
            LEFT JOIN trabajadores t ON c.trabajador_id = t.id
            WHERE 1=1
        """
    
    params = []
    
    if fecha_inicio:
        query += " AND c.fecha >= ?"
        params.append(fecha_inicio)
    if fecha_fin:
        query += " AND c.fecha <= ?"
        params.append(fecha_fin)
    
    query += " ORDER BY c.fecha DESC, c.id DESC"
    
    try:
        df = pd.read_sql_query(query, conn, params=params if params else None)
    except Exception:
        query_simple = """
            SELECT c.*, 
                   t.nombre || ' ' || t.apellido_paterno as trabajador_nombre
            FROM cosechas c
            LEFT JOIN trabajadores t ON c.trabajador_id = t.id
            WHERE 1=1
        """
        if fecha_inicio:
            query_simple += " AND c.fecha >= ?"
        if fecha_fin:
            query_simple += " AND c.fecha <= ?"
        query_simple += " ORDER BY c.fecha DESC, c.id DESC"
        
        df = pd.read_sql_query(query_simple, conn, params=params if params else None)
        df['cajas_disponibles'] = df['numero_cajas']
    
    conn.close()
    return df

def registrar_envio_enfriado(invernadero_id, cantidad_cajas, trabajador_envia_id, trabajador_recibe_id, tipo_envio, presentacion, lote, observaciones):
    """Registra un envío a enfriado con todos los detalles"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        fecha_actual = datetime.now().date()
        hora_actual = datetime.now().time()
        
        # Registrar el envío
        cursor.execute("""
            INSERT INTO envios_enfriado
            (fecha, hora, invernadero_id, trabajador_envia_id, trabajador_recibe_id, 
             tipo_envio, presentacion, cantidad_cajas, lote, observaciones)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (fecha_actual, hora_actual, invernadero_id, trabajador_envia_id, trabajador_recibe_id,
              tipo_envio, presentacion, cantidad_cajas, lote, observaciones))
        
        # Restar cajas del inventario de cosechas
        cursor.execute("PRAGMA table_info(cosechas)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        tiene_cajas_enviadas = 'cajas_enviadas' in column_names
        
        if tiene_cajas_enviadas:
            cursor.execute("""
                SELECT id, numero_cajas, cajas_enviadas
                FROM cosechas
                WHERE fecha <= ? AND (numero_cajas - cajas_enviadas) > 0
                ORDER BY fecha ASC
            """, (fecha_actual,))
            
            cosechas = cursor.fetchall()
            cajas_restantes = cantidad_cajas
            
            for cosecha_id, total_cajas, enviadas in cosechas:
                disponibles = total_cajas - enviadas
                if disponibles > 0:
                    a_descontar = min(disponibles, cajas_restantes)
                    nuevas_enviadas = enviadas + a_descontar
                    cursor.execute("""
                        UPDATE cosechas
                        SET cajas_enviadas = ?
                        WHERE id = ?
                    """, (nuevas_enviadas, cosecha_id))
                    cajas_restantes -= a_descontar
                    if cajas_restantes <= 0:
                        break
        
        conn.commit()
        conn.close()
        
        if tiene_cajas_enviadas and cajas_restantes > 0:
            return True, f"⚠️ Advertencia: Solo se encontraron {cantidad_cajas - cajas_restantes} cajas disponibles. Faltan {cajas_restantes} cajas por registrar en cosechas."
        
        return True, "✅ Envío registrado correctamente"
        
    except Exception as e:
        return False, f"❌ Error al registrar: {str(e)}"

def get_envios_enfriado(fecha_inicio=None, fecha_fin=None, invernadero_id=None):
    """Obtiene registros de envíos con filtros"""
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT e.*,
               i.nombre as invernadero,
               te.nombre || ' ' || te.apellido_paterno as trabajador_envia,
               tr.nombre || ' ' || tr.apellido_paterno as trabajador_recibe
        FROM envios_enfriado e
        LEFT JOIN invernaderos i ON e.invernadero_id = i.id
        LEFT JOIN trabajadores te ON e.trabajador_envia_id = te.id
        LEFT JOIN trabajadores tr ON e.trabajador_recibe_id = tr.id
        WHERE 1=1
    """
    params = []
    
    if fecha_inicio:
        query += " AND e.fecha >= ?"
        params.append(fecha_inicio)
    if fecha_fin:
        query += " AND e.fecha <= ?"
        params.append(fecha_fin)
    if invernadero_id:
        query += " AND e.invernadero_id = ?"
        params.append(invernadero_id)
    
    query += " ORDER BY e.fecha DESC, e.hora DESC"
    
    df = pd.read_sql_query(query, conn, params=params if params else None)
    conn.close()
    return df

def get_stats_envios_avanzado(fecha_inicio=None, fecha_fin=None):
    """Obtiene estadísticas avanzadas de envíos"""
    conn = sqlite3.connect(DB_PATH)
    
    if not fecha_inicio:
        fecha_inicio = datetime.now().date() - timedelta(days=30)
    if not fecha_fin:
        fecha_fin = datetime.now().date()
    
    # Totales generales
    total_cajas = pd.read_sql_query("""
        SELECT SUM(cantidad_cajas) as total 
        FROM envios_enfriado 
        WHERE fecha BETWEEN ? AND ?
    """, conn, params=(fecha_inicio, fecha_fin))['total'][0] or 0
    
    # Envíos por invernadero y tipo
    envios_por_invernadero = pd.read_sql_query("""
        SELECT 
            i.nombre as invernadero,
            e.tipo_envio,
            e.presentacion,
            SUM(e.cantidad_cajas) as cajas_enviadas,
            COUNT(*) as numero_envios
        FROM envios_enfriado e
        LEFT JOIN invernaderos i ON e.invernadero_id = i.id
        WHERE e.fecha BETWEEN ? AND ?
        GROUP BY i.nombre, e.tipo_envio, e.presentacion
        ORDER BY cajas_enviadas DESC
    """, conn, params=(fecha_inicio, fecha_fin))
    
    # Envíos por día
    envios_diarios = pd.read_sql_query("""
        SELECT 
            fecha,
            SUM(cantidad_cajas) as cajas,
            COUNT(*) as envios,
            SUM(CASE WHEN tipo_envio = 'Nacional' THEN cantidad_cajas ELSE 0 END) as nacional,
            SUM(CASE WHEN tipo_envio = 'Exportación' THEN cantidad_cajas ELSE 0 END) as exportacion
        FROM envios_enfriado
        WHERE fecha BETWEEN ? AND ?
        GROUP BY fecha
        ORDER BY fecha
    """, conn, params=(fecha_inicio, fecha_fin))
    
    # Top trabajadores que envían
    top_trabajadores_envian = pd.read_sql_query("""
        SELECT 
            t.nombre || ' ' || t.apellido_paterno as trabajador,
            COUNT(*) as numero_envios,
            SUM(e.cantidad_cajas) as cajas_enviadas
        FROM envios_enfriado e
        LEFT JOIN trabajadores t ON e.trabajador_envia_id = t.id
        WHERE e.fecha BETWEEN ? AND ?
        GROUP BY t.id
        ORDER BY cajas_enviadas DESC
        LIMIT 10
    """, conn, params=(fecha_inicio, fecha_fin))
    
    # Top trabajadores que reciben
    top_trabajadores_reciben = pd.read_sql_query("""
        SELECT 
            t.nombre || ' ' || t.apellido_paterno as trabajador,
            COUNT(*) as numero_envios,
            SUM(e.cantidad_cajas) as cajas_recibidas
        FROM envios_enfriado e
        LEFT JOIN trabajadores t ON e.trabajador_recibe_id = t.id
        WHERE e.fecha BETWEEN ? AND ?
        GROUP BY t.id
        ORDER BY cajas_recibidas DESC
        LIMIT 10
    """, conn, params=(fecha_inicio, fecha_fin))
    
    # Resumen por presentación
    resumen_presentacion = pd.read_sql_query("""
        SELECT 
            presentacion,
            SUM(cantidad_cajas) as cajas,
            COUNT(*) as envios
        FROM envios_enfriado
        WHERE fecha BETWEEN ? AND ?
        GROUP BY presentacion
    """, conn, params=(fecha_inicio, fecha_fin))
    
    conn.close()
    
    return {
        'total_cajas': total_cajas,
        'envios_por_invernadero': envios_por_invernadero,
        'envios_diarios': envios_diarios,
        'top_trabajadores_envian': top_trabajadores_envian,
        'top_trabajadores_reciben': top_trabajadores_reciben,
        'resumen_presentacion': resumen_presentacion
    }

def get_stats_cosecha():
    conn = sqlite3.connect(DB_PATH)
    
    total_cosechas = pd.read_sql_query("SELECT COUNT(*) as total FROM cosechas", conn)['total'][0]
    total_clams = pd.read_sql_query("SELECT SUM(cantidad_clams) as total FROM cosechas", conn)['total'][0]
    total_cajas = pd.read_sql_query("SELECT SUM(numero_cajas) as total FROM cosechas", conn)['total'][0]
    
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(cosechas)")
    columns = cursor.fetchall()
    column_names = [col[1] for col in columns]
    tiene_cajas_enviadas = 'cajas_enviadas' in column_names
    
    if tiene_cajas_enviadas:
        cajas_enviadas = pd.read_sql_query("SELECT SUM(cajas_enviadas) as total FROM cosechas", conn)['total'][0] or 0
    else:
        cajas_enviadas = 0
    
    cosechas_por_tipo = pd.read_sql_query("""
        SELECT tipo_cosecha, COUNT(*) as cantidad, SUM(cantidad_clams) as clams
        FROM cosechas 
        GROUP BY tipo_cosecha
    """, conn)
    
    conn.close()
    
    return {
        'total_cosechas': total_cosechas or 0,
        'total_clams': total_clams or 0,
        'total_cajas': total_cajas or 0,
        'cajas_enviadas': cajas_enviadas,
        'cajas_disponibles': (total_cajas or 0) - (cajas_enviadas or 0),
        'cosechas_por_tipo': cosechas_por_tipo
    }

def get_dashboard_stats():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM trabajadores WHERE estatus = 'activo'")
    total_activos = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT COUNT(*) FROM trabajadores WHERE estatus = 'baja'")
    total_bajas = cursor.fetchone()[0] or 0
    
    df_deptos = pd.read_sql_query("""
        SELECT COALESCE(d.nombre, 'Sin asignar') as departamento, COUNT(*) as cantidad 
        FROM trabajadores t
        LEFT JOIN departamentos d ON t.departamento_id = d.id
        WHERE t.estatus = 'activo' 
        GROUP BY d.nombre
        ORDER BY cantidad DESC
    """, conn)
    
    df_nomina = pd.read_sql_query("""
        SELECT tipo_nomina, COUNT(*) as cantidad 
        FROM trabajadores 
        WHERE estatus = 'activo' 
        GROUP BY tipo_nomina
    """, conn)
    
    inicio_mes = datetime.today().replace(day=1)
    cursor.execute("SELECT COUNT(*) FROM trabajadores WHERE fecha_alta >= ?", (inicio_mes.date(),))
    ingresos_mes = cursor.fetchone()[0] or 0
    
    conn.close()
    
    return {
        'total_activos': total_activos,
        'total_bajas': total_bajas,
        'ingresos_mes': ingresos_mes,
        'df_deptos': df_deptos,
        'df_nomina': df_nomina
    }

def export_to_excel(df, sheet_name="Datos"):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    output.seek(0)
    return output

# ==========================================
# FUNCIONES DE QR
# ==========================================

def generar_qr_trabajador(trabajador_id):
    trabajador = get_worker_by_id(trabajador_id)
    if not trabajador:
        return None, None
    
    contenido = f"{trabajador['id']}|{trabajador['nombre']} {trabajador['apellido_paterno']}|{trabajador['puesto_nombre']}"
    
    if not os.path.exists('qr_codes'):
        os.makedirs('qr_codes')
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(contenido)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    nombre_archivo = f"qr_codes/trabajador_{trabajador['id']}.png"
    img.save(nombre_archivo)
    
    return nombre_archivo, contenido

def generar_qr_masivo(trabajadores_ids):
    generados = []
    carpeta = 'qr_codes/masivos'
    if not os.path.exists(carpeta):
        os.makedirs(carpeta)
    
    for tid in trabajadores_ids:
        trabajador = get_worker_by_id(tid)
        if trabajador:
            contenido = f"{trabajador['id']}|{trabajador['nombre']} {trabajador['apellido_paterno']}|{trabajador['puesto_nombre']}"
            
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(contenido)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            nombre_archivo = f"{carpeta}/qr_{trabajador['id']}_{trabajador['nombre'].replace(' ', '_')}.png"
            img.save(nombre_archivo)
            generados.append(nombre_archivo)
    
    return generados

def crear_pdf_qr(archivos_qr, trabajadores_info):
    try:
        pdf_nombre = "qr_codes/todos_los_qr.pdf"
        c = canvas.Canvas(pdf_nombre, pagesize=letter)
        
        x_pos = 50
        y_pos = 750
        contador = 0
        
        for i, (archivo, info) in enumerate(zip(archivos_qr, trabajadores_info)):
            if os.path.exists(archivo):
                img = ImageReader(archivo)
                c.drawImage(img, x_pos, y_pos - 100, width=100, height=100)
                
                c.drawString(x_pos, y_pos - 110, f"ID: {info['id']}")
                c.drawString(x_pos, y_pos - 120, f"Nombre: {info['nombre']}")
                c.drawString(x_pos, y_pos - 130, f"Puesto: {info['puesto']}")
                
                x_pos += 150
                contador += 1
                
                if contador % 4 == 0:
                    c.showPage()
                    x_pos = 50
                    y_pos = 750
                elif x_pos > 450:
                    x_pos = 50
                    y_pos -= 150
                    
                    if y_pos < 100:
                        c.showPage()
                        x_pos = 50
                        y_pos = 750
        
        c.save()
        return pdf_nombre
    except Exception as e:
        st.error(f"Error al crear PDF: {str(e)}")
        return None

# ==========================================
# INTERFAZ DE REGISTRO RÁPIDO CON QR
# ==========================================

def mostrar_registro_rapido():
    st.header("📱 Registro Rápido con QR")
    
    if 'qr_scaneado' not in st.session_state:
        st.session_state.qr_scaneado = None
    if 'trabajador_temp' not in st.session_state:
        st.session_state.trabajador_temp = None
    if 'clams_rapido' not in st.session_state:
        st.session_state.clams_rapido = 0.0
    if 'cajas_rapido' not in st.session_state:
        st.session_state.cajas_rapido = 0.0
    if 'presentacion_rapido' not in st.session_state:
        st.session_state.presentacion_rapido = "6 oz"
    
    def actualizar_cajas_rapido():
        clams = st.session_state.clams_rapido
        if st.session_state.presentacion_rapido == "12 oz":
            st.session_state.cajas_rapido = clams / 12 if clams > 0 else 0
        else:
            st.session_state.cajas_rapido = clams / 6 if clams > 0 else 0
    
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        qr_scan = st.text_input("🔍 Escanea el código QR", 
                                placeholder="El código aparecerá aquí automáticamente...",
                                key="qr_scan_input")
    
    with col2:
        if st.button("📷 Limpiar", use_container_width=True):
            st.session_state.qr_scaneado = None
            st.session_state.trabajador_temp = None
            st.session_state.clams_rapido = 0.0
            st.session_state.cajas_rapido = 0.0
            st.rerun()
    
    if qr_scan and qr_scan != st.session_state.qr_scaneado:
        st.session_state.qr_scaneado = qr_scan
        try:
            partes = qr_scan.split('|')
            if len(partes) >= 2:
                trabajador_id = partes[0]
                trabajador = get_worker_by_id(trabajador_id)
                if trabajador:
                    st.session_state.trabajador_temp = trabajador
                    st.success(f"✅ Trabajador encontrado: {trabajador['nombre']} {trabajador['apellido_paterno']}")
                else:
                    st.error("❌ Trabajador no encontrado")
        except Exception as e:
            st.error(f"Error: {str(e)}")
    
    if st.session_state.trabajador_temp:
        trabajador = st.session_state.trabajador_temp
        
        st.markdown("---")
        st.subheader("📋 Registrar Evento")
        
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"""
            **Trabajador:** {trabajador['nombre']} {trabajador['apellido_paterno']}
            **ID:** {trabajador['id']}
            **Puesto:** {trabajador['puesto_nombre']}
            """)
        
        fecha_actual = datetime.now()
        dias_espanol = {
            'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miércoles',
            'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'Sábado',
            'Sunday': 'Domingo'
        }
        
        with col2:
            st.info(f"""
            **Fecha:** {fecha_actual.strftime('%d/%m/%Y')}
            **Día:** {dias_espanol[fecha_actual.strftime('%A')]}
            **Semana:** {fecha_actual.isocalendar()[1]}
            **Hora:** {fecha_actual.strftime('%H:%M:%S')}
            """)
        
        st.markdown("---")
        
        # Controles fuera del formulario
        invernaderos = get_invernaderos()
        if invernaderos:
            invernadero_seleccionado = st.selectbox(
                "🌱 Seleccionar Invernadero:",
                invernaderos,
                format_func=lambda x: f"{x[1]} - {x[2]}",
                key="invernadero_select"
            )
            invernadero_id = invernadero_seleccionado[0]
        else:
            st.error("No hay invernaderos registrados")
            invernadero_id = None
        
        modulo = st.selectbox("🔢 Módulo:", list(range(1, 12)), help="Selecciona el módulo de trabajo", key="modulo_select")
        
        tipo_evento = st.selectbox(
            "📌 Tipo de Evento:",
            ["entrada_invernadero", "salida_comer", "regreso_comida", "salida_invernadero"],
            format_func=lambda x: {
                'entrada_invernadero': '🚪 Entrada al Invernadero',
                'salida_comer': '🍽️ Salida a Comer',
                'regreso_comida': '✅ Regreso de Comida',
                'salida_invernadero': '🚪 Salida del Invernadero'
            }[x],
            key="tipo_evento_select"
        )
        
        if tipo_evento == 'entrada_invernadero':
            st.markdown("---")
            st.subheader("📊 Datos de Cosecha")
            
            col1, col2 = st.columns(2)
            with col1:
                tipo_cosecha = st.selectbox("Tipo de Cosecha:", ["Nacional", "Exportación"], key="tipo_cosecha_rapido")
                
                if tipo_cosecha == "Nacional":
                    calidad = st.selectbox("Calidad:", ["Salmon", "Sobretono"])
                else:
                    calidad = None
            
            with col2:
                if tipo_cosecha == "Exportación":
                    presentacion = st.selectbox("Presentación:", ["6 oz", "12 oz"], key="presentacion_rapido_select")
                    st.session_state.presentacion_rapido = presentacion
                else:
                    presentacion = "6 oz"
                    st.session_state.presentacion_rapido = "6 oz"
                    st.info("Presentación automática: 6 oz")
            
            cantidad_clams = st.number_input(
                "Cantidad de Clams:", 
                min_value=0.0, 
                value=st.session_state.clams_rapido, 
                step=1.0,
                key="clams_rapido_input"
            )
            st.session_state.clams_rapido = cantidad_clams
            actualizar_cajas_rapido()
            
            st.text_input("Número de Cajas:", value=f"{st.session_state.cajas_rapido:.2f}", disabled=True)
        
        st.markdown("---")
        
        # Formulario con el botón de enviar
        with st.form("form_registro_rapido"):
            st.write("### Confirmar Registro")
            
            st.info(f"""
            **Resumen del registro:**
            - Trabajador: {trabajador['nombre']} {trabajador['apellido_paterno']}
            - Evento: {tipo_evento}
            """)
            
            if st.form_submit_button("💾 Registrar Evento", type="primary", use_container_width=True):
                success, msg = registrar_evento_asistencia(
                    trabajador['id'],
                    invernadero_id if tipo_evento == 'entrada_invernadero' else None,
                    tipo_evento
                )
                
                if success:
                    st.success(msg)
                    
                    if tipo_evento == 'entrada_invernadero' and 'cantidad_clams' in locals() and cantidad_clams > 0:
                        data_cosecha = {
                            'fecha': fecha_actual.date(),
                            'dia': dias_espanol[fecha_actual.strftime('%A')],
                            'semana': fecha_actual.isocalendar()[1],
                            'trabajador_id': trabajador['id'],
                            'modulo': modulo,
                            'tipo_cosecha': tipo_cosecha,
                            'calidad': calidad,
                            'presentacion': st.session_state.presentacion_rapido,
                            'cantidad_clams': float(st.session_state.clams_rapido),
                            'numero_cajas': float(st.session_state.cajas_rapido)
                        }
                        success2, msg2 = guardar_cosecha(data_cosecha)
                        if success2:
                            st.success(msg2)
                        else:
                            st.error(msg2)
                    
                    st.balloons()
                    st.session_state.qr_scaneado = None
                    st.session_state.trabajador_temp = None
                    st.session_state.clams_rapido = 0.0
                    st.session_state.cajas_rapido = 0.0
                    st.rerun()
                else:
                    st.error(msg)

# ==========================================
# INTERFAZ DE ENVÍOS A ENFRIADO
# ==========================================

def mostrar_envios_enfriado():
    st.header("❄️ Gestión de Envíos a Enfriado")
    
    tab1, tab2, tab3 = st.tabs(["📦 Registrar Envío", "📊 Dashboard Envíos", "📋 Historial"])
    
    with tab1:
        st.subheader("Registrar Envío de Cajas a Enfriado")
        
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
                try:
                    cosechas = get_cosechas()
                    if not cosechas.empty:
                        conn = sqlite3.connect(DB_PATH)
                        query = """
                            SELECT SUM(c.numero_cajas - c.cajas_enviadas) as disponibles
                            FROM cosechas c
                            LEFT JOIN asistencia a ON c.trabajador_id = a.trabajador_id AND c.fecha = a.fecha
                            WHERE a.invernadero_id = ?
                        """
                        disponibles = pd.read_sql_query(query, conn, params=(invernadero_id,))['disponibles'][0] or 0
                        conn.close()
                        st.info(f"📦 Cajas disponibles en {invernadero_seleccionado[1]}: {disponibles:.0f}")
                except:
                    pass
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("👤 Quién entrega las cajas")
            trabajadores = get_all_workers()
            if not trabajadores.empty:
                trabajador_envia = st.selectbox(
                    "Trabajador que entrega:",
                    trabajadores.apply(lambda x: f"{x['id']} - {x['nombre']} {x['apellido_paterno']} ({x['puesto']})", axis=1),
                    key="trabajador_envia"
                )
                trabajador_envia_id = int(trabajador_envia.split(' - ')[0]) if trabajador_envia else None
            else:
                trabajador_envia_id = None
        
        with col2:
            st.subheader("👤 Quién recibe en cámara fría")
            if not trabajadores.empty:
                trabajador_recibe = st.selectbox(
                    "Trabajador que recibe:",
                    trabajadores.apply(lambda x: f"{x['id']} - {x['nombre']} {x['apellido_paterno']} ({x['puesto']})", axis=1),
                    key="trabajador_recibe"
                )
                trabajador_recibe_id = int(trabajador_recibe.split(' - ')[0]) if trabajador_recibe else None
            else:
                trabajador_recibe_id = None
        
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
        
        if st.button("✅ Registrar Envío a Enfriado", type="primary", use_container_width=True):
            if not invernadero_id:
                st.error("Seleccione un invernadero de origen")
            elif not trabajador_envia_id:
                st.error("Seleccione el trabajador que entrega las cajas")
            elif not trabajador_recibe_id:
                st.error("Seleccione el trabajador que recibe en cámara fría")
            elif cantidad_cajas <= 0:
                st.error("Ingrese una cantidad válida de cajas")
            else:
                success, msg = registrar_envio_enfriado(
                    invernadero_id, cantidad_cajas, trabajador_envia_id, 
                    trabajador_recibe_id, tipo_envio, presentacion, lote, observaciones
                )
                if success:
                    st.success(msg)
                    st.balloons()
                else:
                    st.error(msg)
    
    with tab2:
        st.subheader("📊 Dashboard de Envíos a Enfriado")
        
        col1, col2 = st.columns(2)
        with col1:
            fecha_inicio = st.date_input("Fecha inicio:", datetime.now().date() - timedelta(days=30), key="envio_inicio")
        with col2:
            fecha_fin = st.date_input("Fecha fin:", datetime.now().date(), key="envio_fin")
        
        stats_envios = get_stats_envios_avanzado(fecha_inicio, fecha_fin)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📦 Total Cajas Enviadas", f"{stats_envios['total_cajas']:,.0f}")
        with col2:
            st.metric("🚚 Total Envíos Realizados", len(stats_envios['envios_diarios']) if not stats_envios['envios_diarios'].empty else 0)
        with col3:
            promedio_envio = stats_envios['total_cajas'] / max(len(stats_envios['envios_diarios']), 1)
            st.metric("📊 Promedio por Día", f"{promedio_envio:.1f} cajas")
        with col4:
            if not stats_envios['envios_por_invernadero'].empty:
                top_invernadero = stats_envios['envios_por_invernadero'].iloc[0]['invernadero']
                st.metric("🏆 Top Invernadero", top_invernadero)
        
        st.markdown("---")
        
        st.subheader("📅 Evolución de Envíos Diarios")
        if not stats_envios['envios_diarios'].empty:
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            
            fig.add_trace(
                go.Bar(x=stats_envios['envios_diarios']['fecha'], 
                       y=stats_envios['envios_diarios']['cajas'],
                       name="Cajas Enviadas",
                       marker_color='#3498db',
                       opacity=0.7),
                secondary_y=False
            )
            
            fig.add_trace(
                go.Scatter(x=stats_envios['envios_diarios']['fecha'], 
                          y=stats_envios['envios_diarios']['envios'],
                          name="Número de Envíos",
                          mode='lines+markers',
                          line=dict(color='#e74c3c', width=3),
                          marker=dict(size=8, color='#c0392b')),
                secondary_y=True
            )
            
            fig.update_layout(
                title="Evolución de Envíos a Enfriado",
                xaxis_title="Fecha",
                hovermode='x unified',
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)'
            )
            fig.update_yaxes(title_text="Cajas Enviadas", secondary_y=False, gridcolor='#ecf0f1')
            fig.update_yaxes(title_text="Número de Envíos", secondary_y=True, gridcolor='#ecf0f1')
            
            st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📊 Envíos por Invernadero y Tipo")
            if not stats_envios['envios_por_invernadero'].empty:
                fig = px.bar(stats_envios['envios_por_invernadero'], 
                            x='invernadero', y='cajas_enviadas',
                            color='tipo_envio',
                            title='Cajas Enviadas por Invernadero',
                            barmode='group',
                            color_discrete_map={'Nacional': '#2ecc71', 'Exportación': '#e74c3c'},
                            text='cajas_enviadas')
                fig.update_traces(texttemplate='%{text:.0f}', textposition='outside')
                fig.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.subheader("📊 Distribución por Presentación")
            if not stats_envios['resumen_presentacion'].empty:
                fig = px.pie(stats_envios['resumen_presentacion'], 
                            values='cajas', names='presentacion',
                            title='Cajas por Presentación',
                            color_discrete_sequence=['#3498db', '#9b59b6'])
                fig.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🏆 Top Trabajadores que Entregan")
            if not stats_envios['top_trabajadores_envian'].empty:
                fig = px.bar(stats_envios['top_trabajadores_envian'].head(10), 
                            x='trabajador', y='cajas_enviadas',
                            title='Top 10 Trabajadores por Cajas Entregadas',
                            color='cajas_enviadas',
                            color_continuous_scale='blues',
                            text='cajas_enviadas')
                fig.update_traces(texttemplate='%{text:.0f}', textposition='outside')
                fig.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.subheader("🏆 Top Trabajadores que Reciben")
            if not stats_envios['top_trabajadores_reciben'].empty:
                fig = px.bar(stats_envios['top_trabajadores_reciben'].head(10), 
                            x='trabajador', y='cajas_recibidas',
                            title='Top 10 Trabajadores por Cajas Recibidas',
                            color='cajas_recibidas',
                            color_continuous_scale='greens',
                            text='cajas_recibidas')
                fig.update_traces(texttemplate='%{text:.0f}', textposition='outside')
                fig.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")
        
        st.subheader("📋 Resumen de Envíos por Invernadero")
        if not stats_envios['envios_por_invernadero'].empty:
            pivot_envios = stats_envios['envios_por_invernadero'].pivot_table(
                index='invernadero', 
                columns='tipo_envio', 
                values='cajas_enviadas', 
                fill_value=0
            ).reset_index()
            
            if 'Nacional' not in pivot_envios.columns:
                pivot_envios['Nacional'] = 0
            if 'Exportación' not in pivot_envios.columns:
                pivot_envios['Exportación'] = 0
            
            pivot_envios['Total'] = pivot_envios['Nacional'] + pivot_envios['Exportación']
            pivot_envios = pivot_envios.sort_values('Total', ascending=False)
            
            st.dataframe(pivot_envios, use_container_width=True)
    
    with tab3:
        st.subheader("📋 Historial de Envíos")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            fecha_hist_inicio = st.date_input("Fecha inicio histórico:", datetime.now().date() - timedelta(days=30), key="hist_inicio")
        with col2:
            fecha_hist_fin = st.date_input("Fecha fin histórico:", datetime.now().date(), key="hist_fin")
        with col3:
            invernaderos_filtro = [("", "Todos")] + [(id_inv, nombre) for id_inv, nombre, _ in get_invernaderos()]
            invernadero_filtro = st.selectbox(
                "Filtrar por invernadero:",
                invernaderos_filtro,
                format_func=lambda x: x[1] if isinstance(x, tuple) else x
            )
        
        invernadero_id_filtro = invernadero_filtro[0] if invernadero_filtro and invernadero_filtro[0] else None
        
        envios = get_envios_enfriado(fecha_hist_inicio, fecha_hist_fin, invernadero_id_filtro)
        
        if not envios.empty:
            envios_display = envios.copy()
            envios_display['fecha'] = pd.to_datetime(envios_display['fecha']).dt.strftime('%d/%m/%Y')
            if 'hora' in envios_display.columns:
                envios_display['hora'] = envios_display['hora'].astype(str).str[:5]
            
            columns_to_show = ['fecha', 'hora', 'invernadero', 'tipo_envio', 'presentacion', 
                               'cantidad_cajas', 'lote', 'trabajador_envia', 'trabajador_recibe', 'observaciones']
            columns_available = [col for col in columns_to_show if col in envios_display.columns]
            
            st.dataframe(
                envios_display[columns_available],
                use_container_width=True
            )
            
            output = export_to_excel(envios, "Envios_Enfriado")
            st.download_button(
                "📥 Exportar Historial a Excel",
                data=output,
                file_name=f"envios_enfriado_{datetime.now().date()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("No hay registros de envíos en el período seleccionado")

# ==========================================
# INTERFAZ DE DASHBOARD DE ASISTENCIA
# ==========================================

def mostrar_dashboard_asistencia():
    st.header("📊 Dashboard de Asistencia")
    
    col1, col2 = st.columns(2)
    with col1:
        fecha_inicio = st.date_input("📅 Fecha inicio:", datetime.now().date() - timedelta(days=30), key="asist_inicio")
    with col2:
        fecha_fin = st.date_input("📅 Fecha fin:", datetime.now().date(), key="asist_fin")
    
    if st.button("🔄 Actualizar Dashboard", use_container_width=True):
        stats = get_estadisticas_asistencia(fecha_inicio, fecha_fin)
        
        st.markdown("---")
        st.subheader("📈 Indicadores Clave de Asistencia")
        
        total_trabajadores = len(get_all_workers())
        total_registros = stats['registros_por_tipo']['cantidad'].sum() if not stats['registros_por_tipo'].empty else 0
        horas_promedio = stats['horas_promedio']['horas_promedio'].mean() if not stats['horas_promedio'].empty else 0
        tiempo_comida = stats['tiempo_comida']['horas_comida'].mean() if not stats['tiempo_comida'].empty else 0
        visitas_totales = stats['tiempo_invernadero']['visitas'].sum() if not stats['tiempo_invernadero'].empty else 0
        
        total_faltas = stats['faltas_descansos']['faltas'].sum() if not stats['faltas_descansos'].empty else 0
        total_descansos = stats['faltas_descansos']['descansos'].sum() if not stats['faltas_descansos'].empty else 0
        total_presentes = total_registros - total_faltas
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("👥 Total Trabajadores", total_trabajadores, delta=None)
        with col2:
            st.metric("✅ Presentes", total_presentes)
        with col3:
            st.metric("❌ Faltas", total_faltas)
        with col4:
            st.metric("💤 Descansos", total_descansos)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("⏱️ Horas Trabajadas Promedio", f"{horas_promedio:.1f}h")
        with col2:
            st.metric("🍽️ Tiempo Comida Promedio", f"{tiempo_comida:.1f}h")
        with col3:
            st.metric("🏭 Visitas a Invernaderos", f"{visitas_totales:,}")
        with col4:
            tasa_asistencia = (total_presentes / max(total_trabajadores, 1)) * 100
            st.metric("📊 Tasa de Asistencia", f"{tasa_asistencia:.1f}%")
        
        st.markdown("---")
        
        st.subheader("📅 Evolución de Asistencia Diaria")
        if not stats['asistencia_diaria'].empty:
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            
            fig.add_trace(
                go.Bar(x=stats['asistencia_diaria']['fecha'], 
                       y=stats['asistencia_diaria']['total_trabajadores'],
                       name="Total Trabajadores Activos",
                       marker_color='#3498db',
                       opacity=0.7),
                secondary_y=False
            )
            
            fig.add_trace(
                go.Scatter(x=stats['asistencia_diaria']['fecha'], 
                          y=stats['asistencia_diaria']['registraron_entrada'],
                          name="Registraron Asistencia",
                          mode='lines+markers',
                          line=dict(color='#2ecc71', width=3),
                          marker=dict(size=8, color='#27ae60')),
                secondary_y=True
            )
            
            faltas_diarias = stats['asistencia_diaria']['total_trabajadores'] - stats['asistencia_diaria']['registraron_entrada']
            
            fig.add_trace(
                go.Scatter(x=stats['asistencia_diaria']['fecha'], 
                          y=faltas_diarias,
                          name="Faltas",
                          mode='lines+markers',
                          line=dict(color='#e74c3c', width=2, dash='dash'),
                          marker=dict(size=6, color='#c0392b')),
                secondary_y=True
            )
            
            fig.update_layout(
                title="Evolución de Asistencia Diaria",
                xaxis_title="Fecha",
                hovermode='x unified',
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)'
            )
            fig.update_yaxes(title_text="Número de Trabajadores", secondary_y=False, gridcolor='#ecf0f1')
            fig.update_yaxes(title_text="Registros", secondary_y=True, gridcolor='#ecf0f1')
            
            st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")
        
        st.subheader("📊 Faltas y Descansos por Trabajador")
        if not stats['faltas_descansos'].empty:
            col1, col2 = st.columns(2)
            with col1:
                fig = px.bar(stats['faltas_descansos'].sort_values('faltas', ascending=False).head(10),
                            x='trabajador', y='faltas',
                            title='Top 10 Trabajadores con Más Faltas',
                            color='faltas',
                            color_continuous_scale='reds',
                            text='faltas')
                fig.update_traces(texttemplate='%{text}', textposition='outside')
                fig.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                fig = px.bar(stats['faltas_descansos'].sort_values('descansos', ascending=False).head(10),
                            x='trabajador', y='descansos',
                            title='Top 10 Trabajadores con Más Descansos',
                            color='descansos',
                            color_continuous_scale='oranges',
                            text='descansos')
                fig.update_traces(texttemplate='%{text}', textposition='outside')
                fig.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")
        
        st.subheader("🏭 Tiempo Promedio por Invernadero")
        if not stats['tiempo_invernadero'].empty:
            col1, col2 = st.columns(2)
            with col1:
                fig = px.bar(stats['tiempo_invernadero'], 
                            x='invernadero', y='horas_promedio',
                            title='Horas Promedio por Invernadero',
                            color='horas_promedio',
                            color_continuous_scale='oranges',
                            text='horas_promedio')
                fig.update_traces(texttemplate='%{text:.1f}h', textposition='outside')
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                fig = px.bar(stats['tiempo_invernadero'], 
                            x='invernadero', y='visitas',
                            title='Número de Visitas por Invernadero',
                            color='visitas',
                            color_continuous_scale='purples',
                            text='visitas')
                fig.update_traces(texttemplate='%{text}', textposition='outside')
                st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")
        
        st.subheader("📊 Visitas Diarias por Invernadero")
        conn = sqlite3.connect(DB_PATH)
        query_visitas_diarias = """
            SELECT 
                a.fecha,
                i.nombre as invernadero,
                COUNT(*) as visitas
            FROM asistencia a
            LEFT JOIN invernaderos i ON a.invernadero_id = i.id
            WHERE a.fecha BETWEEN ? AND ?
            AND a.hora_entrada IS NOT NULL
            GROUP BY a.fecha, i.nombre
            ORDER BY a.fecha
        """
        df_visitas = pd.read_sql_query(query_visitas_diarias, conn, params=(fecha_inicio, fecha_fin))
        conn.close()
        
        if not df_visitas.empty:
            fig = px.line(df_visitas, x='fecha', y='visitas', color='invernadero',
                         title='Visitas Diarias por Invernadero',
                         markers=True,
                         color_discrete_sequence=px.colors.qualitative.Set1)
            fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', hovermode='x unified')
            st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")
        
        st.subheader("👥 Horas Trabajadas por Trabajador")
        if not stats['horas_promedio'].empty:
            fig = px.bar(stats['horas_promedio'].sort_values('horas_promedio', ascending=False).head(10), 
                        x='trabajador', y='horas_promedio',
                        title='Top 10 Trabajadores por Horas Trabajadas',
                        color='horas_promedio',
                        color_continuous_scale='greens',
                        text='horas_promedio')
            fig.update_traces(texttemplate='%{text:.1f}h', textposition='outside')
            fig.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")
        
        st.subheader("🍽️ Tiempo de Comida por Trabajador")
        if not stats['tiempo_comida'].empty:
            fig = px.bar(stats['tiempo_comida'].sort_values('horas_comida', ascending=False).head(10), 
                        x='trabajador', y='horas_comida',
                        title='Top 10 Trabajadores por Tiempo de Comida',
                        color='horas_comida',
                        color_continuous_scale='reds',
                        text='horas_comida')
            fig.update_traces(texttemplate='%{text:.1f}h', textposition='outside')
            fig.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")
        
        st.subheader("📊 Distribución de Eventos de Asistencia")
        if not stats['registros_por_tipo'].empty:
            mapeo_eventos = {
                'entrada_invernadero': '🚪 Entrada',
                'salida_comer': '🍽️ Salida Comer',
                'regreso_comida': '✅ Regreso Comida',
                'salida_invernadero': '🚪 Salida'
            }
            stats['registros_por_tipo']['tipo'] = stats['registros_por_tipo']['tipo_evento'].map(mapeo_eventos)
            
            col1, col2 = st.columns(2)
            with col1:
                fig = px.pie(stats['registros_por_tipo'], values='cantidad', names='tipo',
                            title='Distribución de Eventos',
                            color_discrete_sequence=px.colors.qualitative.Set3)
                fig.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                fig = px.bar(stats['registros_por_tipo'], x='tipo', y='cantidad',
                            title='Eventos por Tipo',
                            color='cantidad',
                            color_continuous_scale='viridis',
                            text='cantidad')
                fig.update_traces(texttemplate='%{text}', textposition='outside')
                st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")
        
        st.subheader("📋 Resumen de Asistencia del Día")
        
        fecha_hoy = datetime.now().date()
        df_resumen = get_resumen_asistencia_dia(fecha_hoy)
        
        if not df_resumen.empty:
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                total = len(df_resumen)
                st.metric("👥 Total", total)
            with col2:
                presentes = len(df_resumen[df_resumen['estado_actual'] == 'Finalizado']) + len(df_resumen[df_resumen['estado_actual'] == 'En invernadero']) + len(df_resumen[df_resumen['estado_actual'] == 'En comida'])
                st.metric("✅ Presentes", presentes)
            with col3:
                faltas = len(df_resumen[df_resumen['estado_actual'] == 'Falta'])
                st.metric("❌ Faltas", faltas)
            with col4:
                descansos = len(df_resumen[df_resumen['estado_actual'] == 'Descanso'])
                st.metric("💤 Descansos", descansos)
            with col5:
                en_invernadero = len(df_resumen[df_resumen['estado_actual'] == 'En invernadero'])
                st.metric("🏭 En Invernadero", en_invernadero)
            
            st.dataframe(df_resumen, use_container_width=True)
            
            output = export_to_excel(df_resumen, f"Asistencia_{fecha_hoy}")
            st.download_button(
                "📥 Exportar Reporte de Asistencia a Excel",
                data=output,
                file_name=f"reporte_asistencia_{fecha_hoy}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("No hay registros de asistencia para hoy")

# ==========================================
# INTERFAZ DE CONTROL DE ASISTENCIA
# ==========================================

def mostrar_control_asistencia():
    st.header("🕐 Control de Asistencia")
    
    tab1, tab2, tab3, tab4 = st.tabs(["📱 Registrar Asistencia", "📊 Resumen del Día", "📋 Historial", "💤 Registrar Descanso"])
    
    with tab1:
        st.subheader("Registro de Asistencia")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            qr_input = st.text_input("Escanear código QR", 
                                    placeholder="Ej: 1|Juan Pérez|Operario",
                                    key="qr_asistencia")
        with col2:
            if st.button("🔍 Buscar", key="buscar_qr", use_container_width=True):
                if qr_input:
                    try:
                        partes = qr_input.split('|')
                        if len(partes) >= 2:
                            trabajador_id = partes[0]
                            trabajador = get_worker_by_id(trabajador_id)
                            if trabajador:
                                st.session_state['trabajador_asistencia'] = trabajador
                                st.success(f"Trabajador encontrado: {trabajador['nombre']} {trabajador['apellido_paterno']}")
                            else:
                                st.error("Trabajador no encontrado")
                    except Exception as e:
                        st.error(f"Error al procesar QR: {str(e)}")
        
        if 'trabajador_asistencia' in st.session_state:
            trabajador = st.session_state['trabajador_asistencia']
            
            col1, col2 = st.columns([2, 1])
            with col1:
                st.info(f"""
                **Trabajador:** {trabajador['nombre']} {trabajador['apellido_paterno']}
                **Puesto:** {trabajador['puesto_nombre']}
                **Departamento:** {trabajador['departamento_nombre']}
                """)
            
            estado_actual = get_estado_asistencia_actual(trabajador['id'])
            
            with col2:
                if estado_actual:
                    if estado_actual['estado'] == 'activo':
                        st.warning(f"🟢 Estado: En invernadero ({estado_actual['invernadero']})\nDesde: {estado_actual['hora_entrada']}")
                    elif estado_actual['estado'] == 'comida':
                        st.warning(f"🍽️ Estado: En comida\nSalida: {estado_actual['hora_salida_comida']}")
                else:
                    st.success("✅ Estado: Sin registro activo")
            
            st.markdown("---")
            
            if not estado_actual:
                st.subheader("📥 Registrar Entrada")
                invernaderos = get_invernaderos()
                if invernaderos:
                    invernadero_seleccionado = st.selectbox(
                        "Seleccionar invernadero:",
                        invernaderos,
                        format_func=lambda x: f"{x[1]} - {x[2]}",
                        key="invernadero_asistencia"
                    )
                    
                    if st.button("🚪 Registrar Entrada al Invernadero", type="primary", use_container_width=True):
                        success, msg = registrar_evento_asistencia(
                            trabajador['id'],
                            invernadero_seleccionado[0],
                            'entrada_invernadero'
                        )
                        if success:
                            st.success(msg)
                            st.balloons()
                            st.rerun()
                        else:
                            st.error(msg)
                else:
                    st.error("No hay invernaderos registrados")
            
            elif estado_actual['estado'] == 'activo':
                st.subheader("🔄 Opciones Disponibles")
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("🍽️ Salir a Comer", use_container_width=True):
                        success, msg = registrar_evento_asistencia(
                            trabajador['id'],
                            None,
                            'salida_comer'
                        )
                        if success:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
                
                with col2:
                    if st.button("🚪 Salir del Invernadero", use_container_width=True):
                        success, msg = registrar_evento_asistencia(
                            trabajador['id'],
                            None,
                            'salida_invernadero'
                        )
                        if success:
                            st.success(msg)
                            st.balloons()
                            del st.session_state['trabajador_asistencia']
                            st.rerun()
                        else:
                            st.error(msg)
            
            elif estado_actual['estado'] == 'comida':
                st.subheader("🍽️ Registrar Regreso de Comida")
                if st.button("✅ Regresar de Comida", type="primary", use_container_width=True):
                    success, msg = registrar_evento_asistencia(
                        trabajador['id'],
                        None,
                        'regreso_comida'
                    )
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
            
            if st.button("🗑️ Limpiar Selección", use_container_width=True):
                del st.session_state['trabajador_asistencia']
                st.rerun()
    
    with tab2:
        st.subheader("Resumen de Asistencia del Día")
        
        fecha_resumen = st.date_input("Seleccionar fecha:", datetime.now().date(), key="fecha_resumen_asist")
        
        if st.button("Actualizar Resumen", key="btn_resumen_asist", use_container_width=True):
            df_resumen = get_resumen_asistencia_dia(fecha_resumen)
            
            if not df_resumen.empty:
                col1, col2, col3, col4, col5 = st.columns(5)
                with col1:
                    total = len(df_resumen)
                    st.metric("Total Trabajadores", total)
                with col2:
                    presentes = len(df_resumen[df_resumen['estado_actual'] == 'Finalizado']) + len(df_resumen[df_resumen['estado_actual'] == 'En invernadero']) + len(df_resumen[df_resumen['estado_actual'] == 'En comida'])
                    st.metric("Presentes", presentes)
                with col3:
                    faltas = len(df_resumen[df_resumen['estado_actual'] == 'Falta'])
                    st.metric("Faltas", faltas)
                with col4:
                    descansos = len(df_resumen[df_resumen['estado_actual'] == 'Descanso'])
                    st.metric("Descansos", descansos)
                with col5:
                    en_invernadero = len(df_resumen[df_resumen['estado_actual'] == 'En invernadero'])
                    st.metric("En Invernadero", en_invernadero)
                
                st.dataframe(df_resumen, use_container_width=True)
                
                output = export_to_excel(df_resumen, f"Asistencia_{fecha_resumen}")
                st.download_button(
                    "📥 Exportar a Excel",
                    data=output,
                    file_name=f"asistencia_{fecha_resumen}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.info("No hay registros para esta fecha")
    
    with tab3:
        st.subheader("Historial de Asistencia")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            trabajadores_list = get_all_workers()
            trabajadores_opciones = [("", "Todos")] + [(row['id'], f"{row['nombre']} {row['apellido_paterno']}") 
                                                        for _, row in trabajadores_list.iterrows()]
            trabajador_seleccionado = st.selectbox(
                "Filtrar por trabajador:",
                trabajadores_opciones,
                format_func=lambda x: x[1] if isinstance(x, tuple) else x,
                key="hist_trabajador"
            )
        
        with col2:
            fecha_inicio = st.date_input("Fecha inicio:", datetime.now().date() - timedelta(days=30), key="hist_inicio_asist")
        
        with col3:
            fecha_fin = st.date_input("Fecha fin:", datetime.now().date(), key="hist_fin_asist")
        
        tipos_evento = ["Todos", "entrada_invernadero", "salida_comer", "regreso_comida", "salida_invernadero"]
        tipo_evento = st.selectbox("Filtrar por tipo de evento:", tipos_evento, key="tipo_evento_hist")
        
        if st.button("🔍 Buscar Registros", use_container_width=True):
            filtros = {}
            if trabajador_seleccionado and trabajador_seleccionado[0]:
                filtros['trabajador_id'] = trabajador_seleccionado[0]
            filtros['fecha_inicio'] = fecha_inicio
            filtros['fecha_fin'] = fecha_fin
            if tipo_evento != "Todos":
                filtros['tipo_evento'] = tipo_evento
            
            df_historial = get_registros_asistencia(filtros)
            
            if not df_historial.empty:
                mapeo_eventos = {
                    'entrada_invernadero': '🚪 Entrada Invernadero',
                    'salida_comer': '🍽️ Salida a Comer',
                    'regreso_comida': '✅ Regreso de Comida',
                    'salida_invernadero': '🚪 Salida Invernadero'
                }
                df_historial['tipo_evento'] = df_historial['tipo_evento'].map(mapeo_eventos)
                
                st.dataframe(df_historial, use_container_width=True)
                
                st.subheader("📊 Estadísticas del período")
                col1, col2 = st.columns(2)
                with col1:
                    conteo_eventos = df_historial['tipo_evento'].value_counts()
                    fig = px.bar(x=conteo_eventos.index, y=conteo_eventos.values,
                                title='Eventos por Tipo',
                                color=conteo_eventos.values,
                                color_continuous_scale='viridis')
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    conteo_trabajadores = df_historial['trabajador'].value_counts().head(10)
                    fig = px.bar(x=conteo_trabajadores.index, y=conteo_trabajadores.values,
                                title='Top 10 Trabajadores por Eventos',
                                color=conteo_trabajadores.values,
                                color_continuous_scale='plasma')
                    fig.update_layout(xaxis_tickangle=-45)
                    st.plotly_chart(fig, use_container_width=True)
                
                output = export_to_excel(df_historial, "Historial_Asistencia")
                st.download_button(
                    "📥 Exportar Historial a Excel",
                    data=output,
                    file_name=f"historial_asistencia_{datetime.now().date()}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.info("No se encontraron registros con los filtros seleccionados")
    
    with tab4:
        st.subheader("💤 Registrar Descanso de Trabajador")
        
        col1, col2 = st.columns(2)
        
        with col1:
            trabajadores = get_all_workers()
            if not trabajadores.empty:
                trabajador_seleccionado = st.selectbox(
                    "Seleccionar trabajador:",
                    trabajadores.apply(lambda x: f"{x['id']} - {x['nombre']} {x['apellido_paterno']}", axis=1),
                    key="descanso_trabajador"
                )
                trabajador_id = int(trabajador_seleccionado.split(' - ')[0]) if trabajador_seleccionado else None
            else:
                trabajador_id = None
        
        with col2:
            fecha_descanso = st.date_input("Fecha de descanso:", datetime.now().date(), key="fecha_descanso")
        
        tipo_descanso = st.selectbox(
            "Tipo de Descanso:",
            ["Vacaciones", "Permiso", "Enfermedad", "Día de asueto", "Capacitación", "Otro"],
            key="tipo_descanso"
        )
        
        observaciones = st.text_area("Observaciones:", placeholder="Motivo del descanso...", key="obs_descanso")
        
        if st.button("✅ Registrar Descanso", type="primary", use_container_width=True):
            if not trabajador_id:
                st.error("Seleccione un trabajador")
            else:
                success, msg = registrar_descanso(trabajador_id, fecha_descanso, tipo_descanso, observaciones)
                if success:
                    st.success(msg)
                    st.balloons()
                else:
                    st.error(msg)
        
        st.markdown("---")
        st.subheader("📋 Historial de Descansos")
        
        col1, col2 = st.columns(2)
        with col1:
            fecha_desc_inicio = st.date_input("Fecha inicio:", datetime.now().date() - timedelta(days=90), key="desc_inicio")
        with col2:
            fecha_desc_fin = st.date_input("Fecha fin:", datetime.now().date(), key="desc_fin")
        
        descansos = get_descansos(fecha_desc_inicio, fecha_desc_fin)
        
        if not descansos.empty:
            st.dataframe(descansos, use_container_width=True)
            
            output = export_to_excel(descansos, "Descansos")
            st.download_button(
                "📥 Exportar Descansos a Excel",
                data=output,
                file_name=f"descansos_{datetime.now().date()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("No hay registros de descansos en el período seleccionado")

# ==========================================
# INTERFAZ DE COSECHA
# ==========================================

def formulario_cosecha():
    st.header("🌾 Registro de Cosecha")
    
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
    
    st.subheader("📱 Escaneo de Código QR")
    col1, col2 = st.columns([3, 1])
    with col1:
        qr_input = st.text_input("Escanear QR (ID|Nombre|Puesto)", 
                                 placeholder="Ej: 1|Juan Pérez|Operario",
                                 key="qr_input_cosecha")
    with col2:
        if st.button("🔍 Buscar Trabajador", key="buscar_cosecha", use_container_width=True):
            if qr_input:
                try:
                    partes = qr_input.split('|')
                    if len(partes) >= 2:
                        trabajador_id = partes[0]
                        trabajador = get_worker_by_id(trabajador_id)
                        if trabajador:
                            st.session_state['trabajador_seleccionado'] = trabajador
                            st.success(f"Trabajador encontrado: {trabajador['nombre']} {trabajador['apellido_paterno']}")
                        else:
                            st.error("Trabajador no encontrado")
                except Exception as e:
                    st.error(f"Error al procesar QR: {str(e)}")
    
    if 'trabajador_seleccionado' in st.session_state:
        trabajador = st.session_state['trabajador_seleccionado']
        st.info(f"**Trabajador:** {trabajador['nombre']} {trabajador['apellido_paterno']}\n\n**Puesto:** {trabajador['puesto_nombre']}")
    
    st.markdown("---")
    
    st.subheader("📅 Información de Fecha")
    fecha_actual = datetime.now()
    dias_espanol = {
        'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miércoles',
        'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'Sábado',
        'Sunday': 'Domingo'
    }
    dia_espanol = dias_espanol[fecha_actual.strftime('%A')]
    
    col_fecha1, col_fecha2, col_fecha3 = st.columns(3)
    with col_fecha1:
        st.write(f"**Fecha:** {fecha_actual.strftime('%d/%m/%Y')}")
    with col_fecha2:
        st.write(f"**Día:** {dia_espanol}")
    with col_fecha3:
        st.write(f"**Semana:** {fecha_actual.isocalendar()[1]}")
    
    st.markdown("---")
    
    st.subheader("📦 Tipo de Cosecha")
    tipo_cosecha = st.radio("Seleccionar:", ["Nacional", "Exportación"], horizontal=True, key="tipo_cosecha_radio")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if tipo_cosecha == "Nacional":
            calidad = st.selectbox("Calidad:", ["Salmon", "Sobretono"], key="calidad_select")
        else:
            calidad = None
    
    with col2:
        if tipo_cosecha == "Exportación":
            presentacion = st.selectbox("Presentación:", ["6 oz", "12 oz"], key="presentacion_select", on_change=calcular_cajas)
            st.session_state.presentacion_actual = presentacion
        else:
            presentacion = "6 oz"
            st.session_state.presentacion_actual = "6 oz"
            st.info("Presentación automática: 6 oz")
    
    st.markdown("---")
    
    st.subheader("🔢 Módulo")
    modulo = st.radio("Seleccionar módulo:", list(range(1, 12)), horizontal=True, key="modulo_radio")
    
    st.markdown("---")
    
    st.subheader("📊 Cantidades")
    col1, col2 = st.columns(2)
    
    with col1:
        cantidad_clams = st.number_input(
            "Cantidad de Clams:", 
            min_value=0.0, 
            value=st.session_state.clams_value, 
            step=1.0,
            key="clams_input_cosecha",
            on_change=calcular_cajas
        )
        st.session_state.clams_value = cantidad_clams
    
    with col2:
        st.text_input("Número de Cajas:", value=f"{st.session_state.cajas_calculadas:.2f}", disabled=True, key="cajas_display")
    
    st.markdown("---")
    
    with st.form("form_cosecha"):
        st.write("### Confirmar Registro")
        st.write("Verifica que los datos sean correctos antes de guardar.")
        
        st.info(f"""
        **Resumen de la cosecha:**
        - Trabajador: {st.session_state.get('trabajador_seleccionado', {}).get('nombre', 'No seleccionado')} {st.session_state.get('trabajador_seleccionado', {}).get('apellido_paterno', '')}
        - Tipo: {tipo_cosecha}
        - Presentación: {st.session_state.presentacion_actual}
        - Cantidad de Clams: {st.session_state.clams_value:.2f}
        - Número de Cajas: {st.session_state.cajas_calculadas:.2f}
        - Módulo: {modulo if modulo else 'No seleccionado'}
        """)
        
        if st.form_submit_button("💾 Guardar Cosecha", use_container_width=True, type="primary"):
            if 'trabajador_seleccionado' not in st.session_state:
                st.error("Por favor, escanee un código QR o seleccione un trabajador")
            elif not modulo:
                st.error("Por favor, seleccione un módulo")
            elif st.session_state.clams_value <= 0:
                st.error("Por favor, ingrese una cantidad válida de clams")
            else:
                data = {
                    'fecha': fecha_actual.date(),
                    'dia': dia_espanol,
                    'semana': fecha_actual.isocalendar()[1],
                    'trabajador_id': st.session_state['trabajador_seleccionado']['id'],
                    'modulo': modulo,
                    'tipo_cosecha': tipo_cosecha,
                    'calidad': calidad,
                    'presentacion': st.session_state.presentacion_actual,
                    'cantidad_clams': float(st.session_state.clams_value),
                    'numero_cajas': float(st.session_state.cajas_calculadas)
                }
                
                success, msg = guardar_cosecha(data)
                if success:
                    st.success(msg)
                    st.balloons()
                    if 'trabajador_seleccionado' in st.session_state:
                        del st.session_state['trabajador_seleccionado']
                    st.session_state.clams_value = 0.0
                    st.session_state.cajas_calculadas = 0.0
                    st.rerun()
                else:
                    st.error(msg)

# ==========================================
# REPORTES
# ==========================================

def get_report_ingresos_semana():
    hoy = datetime.today()
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    fin_semana = inicio_semana + timedelta(days=6)
    
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT t.id, t.nombre, t.apellido_paterno, t.apellido_materno,
               t.fecha_alta, COALESCE(d.nombre, 'Sin asignar') as departamento, 
               COALESCE(s.nombre, 'Sin asignar') as subdepartamento,
               COALESCE(p.nombre, 'Sin asignar') as puesto, 
               t.tipo_nomina
        FROM trabajadores t
        LEFT JOIN departamentos d ON t.departamento_id = d.id
        LEFT JOIN subdepartamentos s ON t.subdepartamento_id = s.id
        LEFT JOIN puestos p ON t.puesto_id = p.id
        WHERE t.fecha_alta BETWEEN ? AND ?
        ORDER BY t.fecha_alta DESC
    """
    df = pd.read_sql_query(query, conn, params=(inicio_semana.date(), fin_semana.date()))
    conn.close()
    return df, inicio_semana, fin_semana

def get_report_bajas_semana():
    hoy = datetime.today()
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    fin_semana = inicio_semana + timedelta(days=6)
    
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT t.id, t.nombre, t.apellido_paterno, t.apellido_materno,
               t.fecha_baja, COALESCE(d.nombre, 'Sin asignar') as departamento, 
               COALESCE(s.nombre, 'Sin asignar') as subdepartamento,
               COALESCE(p.nombre, 'Sin asignar') as puesto
        FROM trabajadores t
        LEFT JOIN departamentos d ON t.departamento_id = d.id
        LEFT JOIN subdepartamentos s ON t.subdepartamento_id = s.id
        LEFT JOIN puestos p ON t.puesto_id = p.id
        WHERE t.fecha_baja IS NOT NULL
        AND t.fecha_baja BETWEEN ? AND ?
        ORDER BY t.fecha_baja DESC
    """
    df = pd.read_sql_query(query, conn, params=(inicio_semana.date(), fin_semana.date()))
    conn.close()
    return df, inicio_semana, fin_semana

def get_report_nomina_activa(depto_nombre=None, subdepto_nombre=None):
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT t.id, t.nombre, t.apellido_paterno, t.apellido_materno,
               COALESCE(d.nombre, 'Sin asignar') as departamento, 
               COALESCE(s.nombre, 'Sin asignar') as subdepartamento,
               COALESCE(p.nombre, 'Sin asignar') as puesto, 
               t.tipo_nomina,
               t.fecha_alta, t.telefono, t.correo
        FROM trabajadores t
        LEFT JOIN departamentos d ON t.departamento_id = d.id
        LEFT JOIN subdepartamentos s ON t.subdepartamento_id = s.id
        LEFT JOIN puestos p ON t.puesto_id = p.id
        WHERE t.estatus = 'activo'
    """
    params = []
    
    if depto_nombre and depto_nombre != "Todos":
        query += " AND d.nombre = ?"
        params.append(depto_nombre)
    
    if subdepto_nombre and subdepto_nombre != "Todos":
        query += " AND s.nombre = ?"
        params.append(subdepto_nombre)
    
    query += " ORDER BY d.nombre, s.nombre, t.apellido_paterno"
    
    df = pd.read_sql_query(query, conn, params=params if params else None)
    conn.close()
    
    if not df.empty:
        resumen = df.groupby('departamento').size().reset_index(name='cantidad')
    else:
        resumen = pd.DataFrame(columns=['departamento', 'cantidad'])
    
    return df, resumen

# ==========================================
# MENÚ PRINCIPAL EN SIDEBAR
# ==========================================

def mostrar_menu_sidebar():
    """Muestra el menú principal en el sidebar izquierdo"""
    
    st.sidebar.markdown("""
    <div class="sidebar-title">
        <h2>🌾 Sistema Integral</h2>
        <p>Gestión Agrícola</p>
    </div>
    """, unsafe_allow_html=True)
    
    menu_options = {
        "📱 Registro Rápido": {"icon": "📱", "color": "#2ecc71", "desc": "Escanea QR y registra eventos"},
        "🌾 Registro Cosecha": {"icon": "🌾", "color": "#f39c12", "desc": "Registrar producción"},
        "👥 Gestión Personal": {"icon": "👥", "color": "#3498db", "desc": "Alta/baja/editar trabajadores"},
        "📊 Dashboard": {"icon": "📊", "color": "#9b59b6", "desc": "Estadísticas generales"},
        "🕐 Control Asistencia": {"icon": "🕐", "color": "#1abc9c", "desc": "Registro entrada/salida"},
        "❄️ Envíos a Enfriado": {"icon": "❄️", "color": "#e74c3c", "desc": "Cajas a enfriado"},
        "📱 Generar QR": {"icon": "📱", "color": "#34495e", "desc": "Códigos QR para trabajadores"},
        "📋 Reportes": {"icon": "📋", "color": "#95a5a6", "desc": "Reportes y estadísticas"},
        "📚 Catálogos": {"icon": "📚", "color": "#e67e22", "desc": "Departamentos, puestos, etc."},
        "📈 Asistencia Stats": {"icon": "📈", "color": "#16a085", "desc": "Estadísticas asistencia"},
        "🏭 Gestión Invernaderos": {"icon": "🏭", "color": "#27ae60", "desc": "Administrar invernaderos"}
    }
    
    for option, config in menu_options.items():
        if st.sidebar.button(
            f"{config['icon']} {option}", 
            use_container_width=True,
            help=config['desc'],
            key=f"sidebar_{option.replace(' ', '_')}"
        ):
            st.session_state.menu = option
            st.rerun()
    
    st.sidebar.markdown("---")
    st.sidebar.info(
        "**Versión 3.1**\n\n"
        "Sistema Integral de Gestión\n"
        "© 2024"
    )

# ==========================================
# INTERFAZ DE GESTIÓN DE INVERNADEROS
# ==========================================

def mostrar_gestion_invernaderos():
    st.header("🏭 Gestión de Invernaderos")
    
    with st.expander("➕ Agregar Nuevo Invernadero"):
        with st.form("form_invernadero"):
            nombre_invernadero = st.text_input("Nombre del Invernadero *")
            ubicacion_invernadero = st.text_input("Ubicación *")
            
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
                        nuevo_nombre = st.text_input("Nombre", value=nombre)
                        nueva_ubicacion = st.text_input("Ubicación", value=ubicacion)
                        
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

# ==========================================
# FUNCIÓN PRINCIPAL
# ==========================================

def main():
    if 'menu' not in st.session_state:
        st.session_state.menu = "📱 Registro Rápido"
    
    mostrar_menu_sidebar()
    
    if st.session_state.menu == "📱 Registro Rápido":
        mostrar_registro_rapido()
    
    elif st.session_state.menu == "🌾 Registro Cosecha":
        formulario_cosecha()
        with st.expander("📋 Ver Cosechas Registradas"):
            cosechas = get_cosechas()
            if not cosechas.empty:
                st.dataframe(cosechas, use_container_width=True)
                output = export_to_excel(cosechas, "Cosechas")
                st.download_button("📥 Exportar a Excel", data=output,
                                 file_name=f"cosechas_{datetime.now().date()}.xlsx",
                                 mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            else:
                st.info("No hay cosechas registradas")
    
    elif st.session_state.menu == "👥 Gestión Personal":
        st.header("👥 Gestión de Trabajadores")
        
        tab1, tab2 = st.tabs(["Alta de Trabajador", "Buscar/Editar/Baja"])
        
        with tab1:
            with st.form("form_alta", clear_on_submit=True):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    apellido_paterno = st.text_input("Apellido Paterno *")
                    nombre = st.text_input("Nombre *")
                    telefono = st.text_input("Teléfono (10 dígitos)")
                    
                with col2:
                    apellido_materno = st.text_input("Apellido Materno")
                    correo = st.text_input("Correo Electrónico")
                    fecha_alta = st.date_input("Fecha de Alta *", datetime.now())
                    
                with col3:
                    st.write("")
                    st.write("")
                    st.info("* Campos obligatorios")
                
                st.markdown("---")
                
                col4, col5, col6 = st.columns(3)
                with col4:
                    departamentos_list = get_departamentos_nombres()
                    departamento = st.selectbox("Departamento *", departamentos_list if departamentos_list else ["Sin datos"])
                with col5:
                    subdepartamentos_list = get_subdepartamentos_nombres()
                    subdepartamento = st.selectbox("Subdepartamento *", subdepartamentos_list if subdepartamentos_list else ["Sin datos"])
                with col6:
                    tipo_nomina = st.selectbox("Tipo de Nómina *", ["especial", "imss"])
                
                puestos_list = get_puestos_nombres()
                puesto = st.selectbox("Puesto *", puestos_list if puestos_list else ["Sin datos"])
                
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
                search_term = st.text_input("Buscar:", placeholder="Nombre o apellido...")
            with col2:
                estatus_filter = st.selectbox("Estatus", ["todos", "activo", "baja"])
            
            if st.button("🔍 Buscar", use_container_width=True):
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
                                    
                                    if st.button("✏️ Editar", key=f"edit_{row['id']}_{idx}"):
                                        st.session_state['editing_id'] = row['id']
                                
                                if 'baja_id' in st.session_state and st.session_state['baja_id'] == row['id']:
                                    st.warning(f"¿Dar de baja a {st.session_state['baja_nombre']}?")
                                    fecha = st.date_input("Fecha de baja", datetime.now(), key=f"fecha_{row['id']}_{idx}")
                                    col_yes, col_no = st.columns(2)
                                    with col_yes:
                                        if st.button("✅ Confirmar", key=f"conf_{row['id']}_{idx}"):
                                            success, msg = dar_baja(row['id'], fecha)
                                            if success:
                                                st.success(msg)
                                                del st.session_state['baja_id']
                                                del st.session_state['baja_nombre']
                                                st.rerun()
                                            else:
                                                st.error(msg)
                                    with col_no:
                                        if st.button("❌ Cancelar", key=f"can_{row['id']}_{idx}"):
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
                                                ap = st.text_input("Apellido Paterno", worker['apellido_paterno'])
                                                nom = st.text_input("Nombre", worker['nombre'])
                                                tel = st.text_input("Teléfono", worker['telefono'] or "")
                                            
                                            with col_b:
                                                am = st.text_input("Apellido Materno", worker['apellido_materno'] or "")
                                                email = st.text_input("Email", worker['correo'] or "")
                                            
                                            deptos = get_departamentos_nombres()
                                            depto = st.selectbox("Departamento", deptos,
                                                                index=deptos.index(worker['departamento_nombre']) if worker['departamento_nombre'] in deptos else 0)
                                            
                                            subs = get_subdepartamentos_nombres()
                                            sub = st.selectbox("Subdepartamento", subs,
                                                              index=subs.index(worker['subdepartamento_nombre']) if worker['subdepartamento_nombre'] in subs else 0)
                                            
                                            tipo = st.selectbox("Tipo Nómina", ["especial", "imss"],
                                                               index=0 if worker['tipo_nomina']=='especial' else 1)
                                            
                                            puestos = get_puestos_nombres()
                                            p = st.selectbox("Puesto", puestos,
                                                            index=puestos.index(worker['puesto_nombre']) if worker['puesto_nombre'] in puestos else 0)
                                            
                                            est = st.selectbox("Estatus", ["activo", "baja"], 
                                                              index=0 if worker['estatus']=='activo' else 1)
                                            
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
    
    elif st.session_state.menu == "📊 Dashboard":
        st.header("📈 Dashboard General")
        
        st.subheader("👥 Estadísticas de Trabajadores")
        try:
            stats = get_dashboard_stats()
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Activos", stats['total_activos'])
            with col2:
                st.metric("Total Bajas", stats['total_bajas'])
            with col3:
                st.metric("Ingresos del Mes", stats['ingresos_mes'])
            with col4:
                tasa = round((stats['total_bajas'] / max(stats['total_activos'], 1)) * 100, 1)
                st.metric("Tasa de Rotación", f"{tasa}%")
            
            col1, col2 = st.columns(2)
            with col1:
                if not stats['df_deptos'].empty:
                    fig = px.bar(stats['df_deptos'], x='departamento', y='cantidad',
                                title='Trabajadores por Departamento',
                                color='cantidad',
                                color_continuous_scale='blues')
                    st.plotly_chart(fig, use_container_width=True)
            with col2:
                if not stats['df_nomina'].empty:
                    fig = px.pie(stats['df_nomina'], values='cantidad', names='tipo_nomina',
                                title='Distribución por Tipo de Nómina',
                                color_discrete_sequence=['#2ecc71', '#e74c3c'])
                    st.plotly_chart(fig, use_container_width=True)
        
        except Exception as e:
            st.error(f"Error: {str(e)}")
        
        st.markdown("---")
        
        st.subheader("🌾 Estadísticas de Cosecha y Envíos")
        try:
            cosecha_stats = get_stats_cosecha()
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Cosechas", cosecha_stats['total_cosechas'])
            with col2:
                st.metric("Total Clams", f"{cosecha_stats['total_clams']:,.0f}")
            with col3:
                st.metric("Total Cajas Cosechadas", f"{cosecha_stats['total_cajas']:,.0f}")
            with col4:
                st.metric("Cajas Enviadas a Enfriado", f"{cosecha_stats['cajas_enviadas']:,.0f}")
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("📦 Cajas Disponibles en Inventario", f"{cosecha_stats['cajas_disponibles']:,.0f}")
            
            with col2:
                porcentaje_enviado = (cosecha_stats['cajas_enviadas'] / max(cosecha_stats['total_cajas'], 1)) * 100
                st.metric("📊 % de Producción Enviada", f"{porcentaje_enviado:.1f}%")
            
            if not cosecha_stats['cosechas_por_tipo'].empty:
                fig = px.bar(cosecha_stats['cosechas_por_tipo'], x='tipo_cosecha', y='cantidad',
                            title='Cosechas por Tipo',
                            color='cantidad',
                            color_continuous_scale='greens')
                st.plotly_chart(fig, use_container_width=True)
        
        except Exception as e:
            st.error(f"Error: {str(e)}")
        
        st.markdown("---")
        
        st.subheader("❄️ Estadísticas de Envíos a Enfriado")
        try:
            stats_envios = get_stats_envios_avanzado()
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Cajas Enviadas", f"{stats_envios['total_cajas']:,.0f}")
            with col2:
                st.metric("Total Envíos Realizados", len(stats_envios['envios_diarios']) if not stats_envios['envios_diarios'].empty else 0)
            with col3:
                st.metric("Balance en Inventario", f"{cosecha_stats['cajas_disponibles']:,.0f}")
        
        except Exception as e:
            st.error(f"Error: {str(e)}")
        
        st.markdown("---")
        st.subheader("📋 Últimas Cosechas Registradas")
        try:
            cosechas_recientes = get_cosechas()
            if not cosechas_recientes.empty:
                st.dataframe(cosechas_recientes.head(10), use_container_width=True)
            else:
                st.info("No hay cosechas registradas")
        except Exception as e:
            st.error(f"Error al cargar cosechas: {str(e)}")
    
    elif st.session_state.menu == "🕐 Control Asistencia":
        mostrar_control_asistencia()
    
    elif st.session_state.menu == "❄️ Envíos a Enfriado":
        mostrar_envios_enfriado()
    
    elif st.session_state.menu == "📱 Generar QR":
        st.header("📱 Generación de Códigos QR")
        
        tab1, tab2 = st.tabs(["QR Individual", "QR Masivo"])
        
        with tab1:
            st.subheader("Generar QR para un Trabajador")
            
            trabajadores = get_all_workers()
            if not trabajadores.empty:
                trabajador_seleccionado = st.selectbox(
                    "Seleccionar trabajador:",
                    trabajadores.apply(lambda x: f"{x['id']} - {x['nombre']} {x['apellido_paterno']} ({x['puesto']})", axis=1),
                    key="qr_trabajador_select"
                )
                
                if trabajador_seleccionado:
                    worker_id = int(trabajador_seleccionado.split(' - ')[0])
                    
                    if st.button("🔲 Generar QR", use_container_width=True):
                        archivo, contenido = generar_qr_trabajador(worker_id)
                        if archivo:
                            st.success(f"QR generado exitosamente")
                            st.info(f"Contenido del QR: {contenido}")
                            
                            img = Image.open(archivo)
                            st.image(img, caption="Código QR", width=200)
                            
                            with open(archivo, "rb") as file:
                                st.download_button(
                                    label="📥 Descargar QR",
                                    data=file,
                                    file_name=f"qr_{worker_id}.png",
                                    mime="image/png"
                                )
            else:
                st.warning("No hay trabajadores registrados")
        
        with tab2:
            st.subheader("Generación Masiva de QR")
            
            trabajadores = get_all_workers()
            if not trabajadores.empty:
                trabajadores_lista = trabajadores.apply(
                    lambda x: f"{x['id']} - {x['nombre']} {x['apellido_paterno']} ({x['puesto']})", 
                    axis=1
                ).tolist()
                
                seleccionados = st.multiselect("Seleccionar trabajadores:", trabajadores_lista, key="qr_masivo_select")
                
                if seleccionados:
                    ids_seleccionados = [int(s.split(' - ')[0]) for s in seleccionados]
                    st.info(f"Seleccionados: {len(ids_seleccionados)} trabajadores")
                    
                    if st.button("🔲 Generar QR Masivo", use_container_width=True):
                        with st.spinner("Generando códigos QR..."):
                            archivos = generar_qr_masivo(ids_seleccionados)
                            
                            if archivos:
                                st.success(f"Se generaron {len(archivos)} códigos QR")
                                
                                trabajadores_info = []
                                for tid in ids_seleccionados:
                                    worker = get_worker_by_id(tid)
                                    if worker:
                                        trabajadores_info.append({
                                            'id': worker['id'],
                                            'nombre': f"{worker['nombre']} {worker['apellido_paterno']}",
                                            'puesto': worker['puesto_nombre']
                                        })
                                
                                pdf_file = crear_pdf_qr(archivos, trabajadores_info)
                                if pdf_file:
                                    with open(pdf_file, "rb") as file:
                                        st.download_button(
                                            label="📄 Descargar PDF con todos los QR",
                                            data=file,
                                            file_name="todos_los_qr.pdf",
                                            mime="application/pdf"
                                        )
                                
                                st.subheader("Vista previa (primeros 3)")
                                cols = st.columns(3)
                                for i, archivo in enumerate(archivos[:3]):
                                    with cols[i]:
                                        img = Image.open(archivo)
                                        st.image(img, width=150)
            else:
                st.warning("No hay trabajadores registrados")
    
    elif st.session_state.menu == "📋 Reportes":
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
                    st.download_button("📥 Descargar Excel", data=output,
                                     file_name=f"ingresos_{inicio.date()}.xlsx",
                                     mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        
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
                    st.download_button("📥 Descargar Excel", data=output,
                                     file_name=f"bajas_{inicio.date()}.xlsx",
                                     mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        
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
                    col1, col2 = st.columns(2)
                    with col1:
                        st.dataframe(resumen, use_container_width=True)
                    with col2:
                        if not resumen.empty:
                            fig = px.bar(resumen, x='departamento', y='cantidad',
                                        title='Distribución por Departamento',
                                        color='cantidad',
                                        color_continuous_scale='viridis')
                            st.plotly_chart(fig, use_container_width=True)
                    
                    st.subheader("Detalle de Trabajadores")
                    st.dataframe(df, use_container_width=True)
                    
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine="openpyxl") as writer:
                        df.to_excel(writer, index=False, sheet_name="Nómina Activa")
                        resumen.to_excel(writer, index=False, sheet_name="Resumen")
                    output.seek(0)
                    
                    st.download_button("📥 Descargar Excel", data=output,
                                     file_name=f"nomina_activa_{datetime.now().date()}.xlsx",
                                     mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    
    elif st.session_state.menu == "📚 Catálogos":
        st.header("📋 Gestión de Catálogos")
        
        tab1, tab2, tab3 = st.tabs(["🏢 Departamentos", "📂 Subdepartamentos", "💼 Puestos"])
        
        with tab1:
            st.subheader("Administrar Departamentos")
            
            with st.form("new_depto"):
                new_depto = st.text_input("Nuevo departamento")
                if st.form_submit_button("➕ Agregar", use_container_width=True):
                    if new_depto:
                        success, msg = add_catalog_item("departamentos", new_depto)
                        if success:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
            
            st.markdown("---")
            
            deptos = get_departamentos()
            
            if deptos:
                for id_depto, nombre in deptos:
                    with st.container():
                        cols = st.columns([4, 1, 1])
                        
                        with cols[0]:
                            st.write(f"**{nombre}**")
                        
                        with cols[1]:
                            if st.button("✏️ Editar", key=f"edit_depto_{id_depto}"):
                                st.session_state[f'editing_depto_{id_depto}'] = True
                        
                        with cols[2]:
                            if st.button("🗑️ Eliminar", key=f"del_depto_{id_depto}"):
                                st.session_state[f'deleting_depto_{id_depto}'] = True
                        
                        if st.session_state.get(f'editing_depto_{id_depto}', False):
                            with st.form(key=f"form_edit_depto_{id_depto}"):
                                nuevo_nombre = st.text_input("Editar nombre", value=nombre)
                                col1, col2 = st.columns(2)
                                with col1:
                                    if st.form_submit_button("💾 Guardar"):
                                        success, msg = update_catalog_item("departamentos", id_depto, nuevo_nombre)
                                        if success:
                                            st.success(msg)
                                            del st.session_state[f'editing_depto_{id_depto}']
                                            st.rerun()
                                        else:
                                            st.error(msg)
                                with col2:
                                    if st.form_submit_button("❌ Cancelar"):
                                        del st.session_state[f'editing_depto_{id_depto}']
                                        st.rerun()
                        
                        if st.session_state.get(f'deleting_depto_{id_depto}', False):
                            st.warning(f"¿Eliminar '{nombre}'?")
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.button("✅ Sí, eliminar", key=f"conf_del_depto_{id_depto}"):
                                    success, msg = delete_catalog_item("departamentos", id_depto)
                                    if success:
                                        st.success(msg)
                                        del st.session_state[f'deleting_depto_{id_depto}']
                                        st.rerun()
                                    else:
                                        st.error(msg)
                            with col2:
                                if st.button("❌ No, cancelar", key=f"cancel_del_depto_{id_depto}"):
                                    del st.session_state[f'deleting_depto_{id_depto}']
                                    st.rerun()
                        
                        st.markdown("---")
            else:
                st.info("No hay departamentos. Agrega uno usando el formulario de arriba.")
        
        with tab2:
            st.subheader("Administrar Subdepartamentos")
            
            with st.form("new_subdepto"):
                new_subdepto = st.text_input("Nuevo subdepartamento")
                if st.form_submit_button("➕ Agregar", use_container_width=True):
                    if new_subdepto:
                        success, msg = add_catalog_item("subdepartamentos", new_subdepto)
                        if success:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
            
            st.markdown("---")
            
            subdeptos = get_subdepartamentos()
            
            if subdeptos:
                for id_sub, nombre in subdeptos:
                    with st.container():
                        cols = st.columns([4, 1, 1])
                        
                        with cols[0]:
                            st.write(f"**{nombre}**")
                        
                        with cols[1]:
                            if st.button("✏️ Editar", key=f"edit_sub_{id_sub}"):
                                st.session_state[f'editing_sub_{id_sub}'] = True
                        
                        with cols[2]:
                            if st.button("🗑️ Eliminar", key=f"del_sub_{id_sub}"):
                                st.session_state[f'deleting_sub_{id_sub}'] = True
                        
                        if st.session_state.get(f'editing_sub_{id_sub}', False):
                            with st.form(key=f"form_edit_sub_{id_sub}"):
                                nuevo_nombre = st.text_input("Editar nombre", value=nombre)
                                col1, col2 = st.columns(2)
                                with col1:
                                    if st.form_submit_button("💾 Guardar"):
                                        success, msg = update_catalog_item("subdepartamentos", id_sub, nuevo_nombre)
                                        if success:
                                            st.success(msg)
                                            del st.session_state[f'editing_sub_{id_sub}']
                                            st.rerun()
                                        else:
                                            st.error(msg)
                                with col2:
                                    if st.form_submit_button("❌ Cancelar"):
                                        del st.session_state[f'editing_sub_{id_sub}']
                                        st.rerun()
                        
                        if st.session_state.get(f'deleting_sub_{id_sub}', False):
                            st.warning(f"¿Eliminar '{nombre}'?")
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.button("✅ Sí, eliminar", key=f"conf_del_sub_{id_sub}"):
                                    success, msg = delete_catalog_item("subdepartamentos", id_sub)
                                    if success:
                                        st.success(msg)
                                        del st.session_state[f'deleting_sub_{id_sub}']
                                        st.rerun()
                                    else:
                                        st.error(msg)
                            with col2:
                                if st.button("❌ No, cancelar", key=f"cancel_del_sub_{id_sub}"):
                                    del st.session_state[f'deleting_sub_{id_sub}']
                                    st.rerun()
                        
                        st.markdown("---")
            else:
                st.info("No hay subdepartamentos. Agrega uno usando el formulario de arriba.")
        
        with tab3:
            st.subheader("Administrar Puestos")
            
            with st.form("new_puesto"):
                new_puesto = st.text_input("Nuevo puesto")
                if st.form_submit_button("➕ Agregar", use_container_width=True):
                    if new_puesto:
                        success, msg = add_catalog_item("puestos", new_puesto)
                        if success:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
            
            st.markdown("---")
            
            puestos = get_puestos()
            
            if puestos:
                for id_puesto, nombre in puestos:
                    with st.container():
                        cols = st.columns([4, 1, 1])
                        
                        with cols[0]:
                            st.write(f"**{nombre}**")
                        
                        with cols[1]:
                            if st.button("✏️ Editar", key=f"edit_puesto_{id_puesto}"):
                                st.session_state[f'editing_puesto_{id_puesto}'] = True
                        
                        with cols[2]:
                            if st.button("🗑️ Eliminar", key=f"del_puesto_{id_puesto}"):
                                st.session_state[f'deleting_puesto_{id_puesto}'] = True
                        
                        if st.session_state.get(f'editing_puesto_{id_puesto}', False):
                            with st.form(key=f"form_edit_puesto_{id_puesto}"):
                                nuevo_nombre = st.text_input("Editar nombre", value=nombre)
                                col1, col2 = st.columns(2)
                                with col1:
                                    if st.form_submit_button("💾 Guardar"):
                                        success, msg = update_catalog_item("puestos", id_puesto, nuevo_nombre)
                                        if success:
                                            st.success(msg)
                                            del st.session_state[f'editing_puesto_{id_puesto}']
                                            st.rerun()
                                        else:
                                            st.error(msg)
                                with col2:
                                    if st.form_submit_button("❌ Cancelar"):
                                        del st.session_state[f'editing_puesto_{id_puesto}']
                                        st.rerun()
                        
                        if st.session_state.get(f'deleting_puesto_{id_puesto}', False):
                            st.warning(f"¿Eliminar '{nombre}'?")
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.button("✅ Sí, eliminar", key=f"conf_del_puesto_{id_puesto}"):
                                    success, msg = delete_catalog_item("puestos", id_puesto)
                                    if success:
                                        st.success(msg)
                                        del st.session_state[f'deleting_puesto_{id_puesto}']
                                        st.rerun()
                                    else:
                                        st.error(msg)
                            with col2:
                                if st.button("❌ No, cancelar", key=f"cancel_del_puesto_{id_puesto}"):
                                    del st.session_state[f'deleting_puesto_{id_puesto}']
                                    st.rerun()
                        
                        st.markdown("---")
            else:
                st.info("No hay puestos. Agrega uno usando el formulario de arriba.")
    
    elif st.session_state.menu == "📈 Asistencia Stats":
        mostrar_dashboard_asistencia()
    
    elif st.session_state.menu == "🏭 Gestión Invernaderos":
        mostrar_gestion_invernaderos()

# ==========================================
# EJECUTAR APLICACIÓN
# ==========================================

if __name__ == "__main__":
    main()
