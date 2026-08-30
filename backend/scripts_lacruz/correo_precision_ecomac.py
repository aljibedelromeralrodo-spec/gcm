"""Correo de seguimiento: precisión cifras solo-Ecomac + desglose por ejecutiva."""
import base64
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
import sys
sys.path.insert(0, "/app/backend")

H3 = "margin:16px 0 6px;color:#14213d;font-size:15px;border-bottom:2px solid #c9a227;padding-bottom:3px;max-width:640px"

CUERPO = f"""
<div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:1.6;color:#1a1a1a;max-width:640px">
<p>Estimadas y estimados:</p>
<p>Como complemento al informe que les hice llegar, y para dejar las cifras del trimestre referidas
<b>exclusivamente a Ecomac</b>, les comparto la precisi&oacute;n que corresponde junto con un detalle que
estim&eacute; &uacute;til para su propio seguimiento comercial.</p>

<h3 style="{H3}">Precisi&oacute;n de cifras del trimestre</h3>
<p>Nuestra mesa de evaluaci&oacute;n emiti&oacute; 191 cartas de aprobaci&oacute;n durante el &uacute;ltimo trimestre
considerando todos los canales que gestionamos. De ellas, <b>75 corresponden espec&iacute;ficamente a clientes
Ecomac</b> (30 en junio, 23 en julio y 22 en agosto), cada una vinculada al correo de la ejecutiva que deriv&oacute;
al cliente. Es esta &uacute;ltima cifra la que refleja con exactitud nuestra gesti&oacute;n conjunta, y contra
16 escrituraciones del per&iacute;odo confirma lo esencial: <b>estamos aprobando en verde hoy las operaciones
que escriturar&aacute;n cuando sus proyectos se entreguen.</b></p>

<h3 style="{H3}">Detalle por ejecutiva Ecomac (aprobaciones del trimestre)</h3>
<table border="1" cellpadding="4" cellspacing="0" width="100%"
 style="border-collapse:collapse;border:1px solid #b9c0cc;font-size:12px;margin:8px 0;max-width:640px">
<tr style="background:#14213d;color:#fff"><th style="padding:5px;text-align:left">Ejecutiva</th>
<th style="padding:5px">Jun</th><th style="padding:5px">Jul</th><th style="padding:5px">Ago</th><th style="padding:5px">Total</th></tr>
<tr><td style="padding:4px">Ximena G&oacute;mez</td><td align="center">8</td><td align="center">8</td><td align="center">11</td><td align="center"><b>27</b></td></tr>
<tr style="background:#f6f8f6"><td style="padding:4px">Carla Paz</td><td align="center">9</td><td align="center">11</td><td align="center">2</td><td align="center"><b>22</b></td></tr>
<tr><td style="padding:4px">Gina G&oacute;mez</td><td align="center">2</td><td align="center">2</td><td align="center">4</td><td align="center"><b>8</b></td></tr>
<tr style="background:#f6f8f6"><td style="padding:4px">W. Guerrero</td><td align="center">4</td><td align="center">1</td><td align="center">1</td><td align="center"><b>6</b></td></tr>
<tr><td style="padding:4px">Gabriela Mu&ntilde;oz</td><td align="center">2</td><td align="center">&mdash;</td><td align="center">1</td><td align="center"><b>3</b></td></tr>
<tr style="background:#f6f8f6"><td style="padding:4px">Otras ejecutivas (Sara G., Marisela, Amalia, Rita, Luc&iacute;a y m&aacute;s)</td>
<td align="center">5</td><td align="center">1</td><td align="center">3</td><td align="center"><b>9</b></td></tr>
<tr style="background:#f0e9d2"><td style="padding:4px"><b>TOTAL ECOMAC</b></td><td align="center"><b>30</b></td>
<td align="center"><b>23</b></td><td align="center"><b>22</b></td><td align="center"><b>75</b></td></tr>
</table>
<p>Destaca la consistencia de <b>Ximena G&oacute;mez</b> (aprobaciones todos los meses, al alza) y el volumen de
<b>Carla Paz</b>: entre ambas concentran dos tercios de las aprobaciones del trimestre.</p>

<p>Todo lo dem&aacute;s informado se mantiene plenamente vigente: mediana de respuesta de 11,3 horas, m&aacute;s de
UF 170.000 escrituradas en el ciclo de la alianza y un equipo comprometido con cada reserva de Ecomac.</p>
<p>Quedo atento a cualquier consulta sobre el detalle.
<b>Mantengamos esta alianza que funciona.</b></p>
<p>Atentamente,<br/><br/>
<b>Gerardo Barraza</b><br/>
Central Mutuos Ltda.<br/>
Av. La Dehesa 1822, Of. 511, Torre Sur &middot; Lo Barnechea<br/>
www.centralmutuos.cl</p>
</div>
"""

import email_service as es
r = es.send_mail("gerardo.ext@centralmutuos.cl",
                 "Precisión de cifras del trimestre — detalle exclusivo Ecomac por ejecutiva",
                 CUERPO)
print("ENCOLADO:", r)
