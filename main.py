INSERT INTO perfiles_usuario (id, nombre_usuario, email, nombre, rol, activo, permisos)
VALUES (
    (SELECT id FROM auth.users WHERE email = 'admin@sistema.com'),
    'admin',
    'admin@sistema.com',
    'Administrador',
    'admin',
    true,
    '{
        "registro_cosecha": true,
        "dashboard": true,
        "proyecciones": true,
        "control_asistencia": true,
        "avance_cosecha": true,
        "traslado_camara_fria": true,
        "gestion_merma": true,
        "cajas_mesa": true,
        "registros_qr": true,
        "reportes": true,
        "gestion_invernaderos": true,
        "gestion_personal": true,
        "gestion_usuarios": true,
        "generar_qr": true,
        "catalogos": true,
        "cierre_dia": true
    }'::jsonb
);
