# Guía rápida de bodega · Dulcesitos Castillo

> Guarda esta guía junto al equipo. La aplicación siempre muestra el estado del lector en la esquina superior derecha.

## Roles

- **Administrador único:** el propietario. Configura su acceso solo en el primer arranque. No existen otros administradores ni un módulo para asignar ese rol.
- **Operador:** entra únicamente con un código vigente emitido por el administrador. No ve opciones de administración, catálogo ni configuración del lector.
- El operador puede **validar productos, ajustar el stock contado y registrar manualmente** cuando el lector falla.

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

No hay un botón de administración en la estación del operador. Si necesitas al administrador, cierra la sesión y él entrará desde **Acceso administración** en la pantalla de ingreso.

## Calibración

1. Verifica que el archivo maestro diga **CATÁLOGO VIGENTE**.
2. Escanea un producto que sepas que existe.
3. Espera el aviso verde:

   **Prueba Match Sincronización OK**

4. Pulsa **Comenzar registro**.

Si el aviso no aparece, no comiences el inventario: revisa el producto escaneado, la conexión USB y pide apoyo al administrador. Si el lector no responde, puedes usar **Registro manual**.

## Durante el registro

| Color | Significado | Qué hacer |
| --- | --- | --- |
| 🟢 Verde | Producto registrado | Continúa con el siguiente. |
| 🟡 Ámbar | Producto duplicado o manual | Revisa si es correcto antes de continuar. |
| 🔴 Rojo | Código no encontrado | Conserva el producto aparte; usa el registro manual o avisa al administrador. |

- Cada lectura se guarda inmediatamente.
- Si te equivocaste, pulsa **Deshacer última lectura**.
- Si el lector deja de estar **ACTIVO**, pulsa **Revisar lector y calibrar**.
- No cierres la aplicación durante una lectura.

### Ajustar el stock contado

1. Escanea el producto.
2. En el panel derecho, revisa **Stock del catálogo**.
3. Escribe el **stock contado** en el campo y pulsa **Guardar stock**.
4. El ajuste queda con fecha, hora y operador. Puedes retirarlo con **Quitar ajuste**.
5. En el archivo de actualización se reemplaza el stock y se agregan las columnas **STOCK ORIGINAL**, **STOCK CONTADO** y **DIFERENCIA DE STOCK**.

Si no ajustas el stock, se conserva el valor del catálogo.

### Registro manual cuando el lector falla

1. Pulsa **Registro manual**. El lector queda en pausa.
2. Escribe el **código** y la **descripción** del producto.
3. Escribe la **novedad o motivo** (obligatoria).
4. Opcionalmente escribe el stock contado.
5. Pulsa **Registrar manual**.
6. El registro queda marcado como **MANUAL** y la novedad aparece en la tabla, el Excel, el TXT y el PDF.

Si el código existe en el catálogo, se usan los datos oficiales del producto. Si no existe, se incluye como producto manual en los archivos de salida. Un producto dado de baja no se puede registrar manualmente.

## Cierre

1. Pulsa **Proceso/Registro terminado**.
2. Escribe tu nombre tal como aparece en la sesión.
3. Escribe tu código de acceso vigente o pide la clave al administrador.
4. Espera la confirmación.
5. Revisa el **reporte visual** y abre o imprime el PDF.
6. Los archivos quedan en `C:\dulcesito_castillo\salidas`.

## Si tienes que salir antes de terminar

Puedes pulsar **Salir**. Tus registros quedarán guardados. Cuando vuelvas a ingresar con el mismo operador, el sistema te ofrecerá reanudar la sesión.

Si el administrador revoca o vence tu código mientras trabajas, la estación se bloquea en segundos. Los registros se conservan y el cierre se puede autorizar con la clave del administrador.

## Para el administrador

La cuenta de administración es única y se configura solo en el primer arranque. No hay forma de crear un segundo administrador, ceder el rol ni cambiar de administrador. El panel solo se abre desde la pantalla de ingreso.

1. Cierra la sesión del operador si hay una abierta.
2. Pulsa **Acceso administración**.
3. Ingresa cédula y clave de administración.
4. **Accesos → Generar código** para un operador nuevo o una renovación.
5. Copia el código en ese momento: no se vuelve a mostrar.
6. **Operadores** permite renovar o revocar accesos.
7. **Catálogo** permite crear un producto local, darlo de baja o reactivarlo. El archivo maestro original no se modifica.
8. **Lector** permite cambiar entre USB HID y puerto serie.
9. **Historial** consulta sesiones y archivos generados.
10. **Crear respaldo** guarda una copia de la base local.

Los cambios de catálogo rigen para sesiones nuevas. Una sesión en curso conserva su copia del catálogo hasta finalizar; al aplicarse, la estación pide calibrar de nuevo.

Nunca compartas la clave de administración por canales inseguros.

## Solución de problemas

| Situación | Qué hacer |
| --- | --- |
| El lector no aparece | Revisa el cable USB, pulsa **Volver a detectar** y calibra. |
| El código no se lee | Usa **Registro manual**, escribe código, descripción y novedad. |
| El código no existe en el Excel | Regístralo manualmente. Queda en la salida con la novedad. |
| El producto está dado de baja | No se puede registrar; el administrador debe reactivarlo en **Catálogo**. |
| El código venció o fue revocado | La estación se bloquea. El administrador debe renovar el acceso y autorizar el cierre. |
| La aplicación no abre | Ejecuta `diagnostico.bat` o revisa `%LOCALAPPDATA%\DulcesitosCastillo\logs`. |
| No se puede escribir en `C:\dulcesito_castillo` | Ejecuta con permisos sobre `C:\` o instala en una carpeta autorizada. |

## Contacto

Proyecto formativo Dulcesitos_Castillo · SENA · Carlos Castillo.
