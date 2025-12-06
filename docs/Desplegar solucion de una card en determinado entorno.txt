Desplegar solucion de una card en determinado entorno:
¿Ya confirmó que no habrá conflicto de migraciones y tiene luz verde para desplegar el repositorio [repo] 
en el entorno [entorno] ?
En caso de sí, continuar, si no, revisar que rama es la que esta desplegada actualmente para dicho entorno.
Usar el historial del build para el repo en cuestion. Si es la rama por defecto del entorno (dev o staging) 
entonces se puede pasar al siguiente paso, si no es el caso, entonces preguntarle al autor de la rama si no 
hay problema con desplegar una nueva y pedirle que haga downgrade en caso de que haya hecho nuevas migraciones 
(mas eficiente seria, revisar la rama, si tiene nuevas migraciones entonces hacer la solicitud).
Desplegando [repo] en [entorno]
Una vez el entorno este preparado, correr job correspondiente al repo, la rama y el entorno.
Notificar el estado exitoso o fallido del despliegue. En caso de fallido mostrar logs o mensajes de 
error si es posible.
El despliegue ha sido exitoso
El despliegue ha fallado: [error]
 Desea desplegar mientras tanto la rama [rama por defecto] para evitar bloquear el uso de [repo] en [entorno]?
Desplegando [rama por defecto] en [entorno]