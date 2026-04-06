-- Agregar campo lineas_totales a la tabla invernaderos si no existe
ALTER TABLE invernaderos ADD COLUMN IF NOT EXISTS lineas_totales INTEGER DEFAULT 40;

-- Actualizar invernaderos existentes con valores por defecto
UPDATE invernaderos SET lineas_totales = 40 WHERE lineas_totales IS NULL;

-- Crear tabla de cierres de día si no existe
CREATE TABLE IF NOT EXISTS cierres_dia (
    id SERIAL PRIMARY KEY,
    fecha DATE UNIQUE NOT NULL,
    cerrado_por TEXT NOT NULL,
    reporte JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Crear tabla de configuración del sistema si no existe
CREATE TABLE IF NOT EXISTS configuracion_sistema (
    id SERIAL PRIMARY KEY,
    clave TEXT UNIQUE NOT NULL,
    valor TEXT,
    descripcion TEXT,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Insertar configuraciones por defecto
INSERT INTO configuracion_sistema (clave, valor, descripcion) VALUES
('registro_manual_asistencia', 'true', 'Permitir registro manual de asistencia'),
('registro_manual_cosecha', 'true', 'Permitir registro manual de cosecha')
ON CONFLICT (clave) DO NOTHING;
