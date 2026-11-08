# Guía rápida de bodega · Dulcesitos Castillo

> Guarda esta guía junto al equipo. La aplicación siempre muestra el estado del lector en la esquina superior derecha.

## Antes de abrir

- [ ] El archivo maestro está en `C:\dulcesito_castillo`.
- [ ] El lector USB está conectado.
- [ ] El administrador entregó un código vigente al operador.
- [ ] La estación tiene energía y el equipo está desbloqueado.

## Ingreso del operador

1. Escribe tu **cédula**.
2. Escribe tu **código de acceso** con el formato `DLC-XXXX-XXXX-XXXX`.
3. Pulsa **Ingresar a la estación**.

Si es tu primera vez, el administrador te dará un código de activación. Úsalo en **Activar código** junto con tu nombre completo, cédula y correo.

## Calibración

1. Verifica que el archivo maestro diga **CATÁLOGO VIGENTE**.
2. Escanea un producto que sepas que existe.
3. Espera el aviso verde:

   **Prueba Match Sincronización OK**

4. Pulsa **Comenzar registro**.

Si el aviso no aparece, no comiences el inventario: revisa el producto escaneado, la conexión USB y pide apoyo al administrador.

## Durante el registro

| Color | Significado | Qué hacer |
| --- | --- | --- |
| 🟢 Verde | Producto registrado | Continúa con el siguiente. |
| 🟡 Ámbar | Producto duplicado | No se agregó otra vez. Revisa si es correcto. |
| 🔴 Rojo | Código no encontrado | Conserva el producto aparte y avisa al administrador. |

- Cada lectura se guarda inmediatamente.
- Si te equivocaste, pulsa **Deshacer última lectura**.
- Si el lector deja de estar **ACTIVO**, pulsa **Revisar lector y calibrar**.
- No cierres la aplicación durante una lectura.

## Cierre

1. Pulsa **Proceso/Registro terminado**.
2. Escribe tu nombre tal como aparece en la sesión.
3. Escribe tu código de acceso vigente o pide la clave al administrador.
4. Espera la confirmación.
5. Revisa el **reporte visual** y abre o imprime el PDF.
6. Los archivos quedan en `C:\dulcesito_castillo\salidas`.

## Si tienes que salir antes de terminar

Puedes pulsar **Salir**. Tus registros quedarán guardados. Cuando vuelvas a ingresar con el mismo operador, el sistema te ofrecerá reanudar la sesión.

## Para el administrador

1. Abre **Admin** desde la barra superior.
2. Ingresa cédula y clave de administración.
3. **Accesos → Generar código** para un operador nuevo o una renovación.
4. Copia el código en ese momento: no se vuelve a mostrar.
5. **Operadores** permite renovar o revocar accesos.
6. **Lector** permite cambiar entre USB HID y puerto serie.
7. **Historial** consulta sesiones y archivos generados.
8. **Crear respaldo** guarda una copia de la base local.

Nunca compartas la clave de administración por canales inseguros.

## Contacto

Proyecto formativo Dulcesitos_Castillo · SENA · Carlos Castillo.
