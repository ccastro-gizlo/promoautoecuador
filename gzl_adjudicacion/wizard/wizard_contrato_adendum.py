# -*- coding: utf-8 -*-

from odoo import api, fields, models, tools, SUPERUSER_ID
from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta, date
from odoo.exceptions import ValidationError
import numpy_financial as npf
import math


class WizardContratoAdendum(models.Model):
    _name = 'wizard.contrato.adendum'
    _description = 'Contrato Adendum'


    contrato_id = fields.Many2one('contrato',string="Contrato")
    socio_id = fields.Many2one('res.partner',string="Socio")
    ejecutado = fields.Boolean(string="Ejecutado", default = False)
    monto_financiamiento = fields.Monetary(
        string='Monto Financiamiento', currency_field='currency_id', track_visibility='onchange')
    plazo_meses = fields.Many2one('numero.meses',default=lambda self: self.env.ref('gzl_adjudicacion.{0}'.format('numero_meses60')).id ,track_visibility='onchange' )

    currency_id = fields.Many2one(
        'res.currency', readonly=True, default=lambda self: self.env.company.currency_id)
    ##valores anteriores
    monto_financiamiento_anterior = fields.Monetary(
        string='Monto Financiamiento', currency_field='currency_id', track_visibility='onchange')
    plazo_meses_anterior = fields.Many2one('numero.meses',default=lambda self: self.env.ref('gzl_adjudicacion.{0}'.format('numero_meses60')).id ,track_visibility='onchange' )
    cuota_anterior = fields.Monetary(currency_field='currency_id', track_visibility='onchange')
    observacion = fields.Char(string='Observacion')
    def ejecutar_cambio(self,):

        if   self.contrato_id.ejecutado:
            raise ValidationError("El contrato solo puede realizar un adendum")
        elif self.contrato_id.state !='activo':
            raise ValidationError("El contrato solo puede realizar un adendum en estado activo")
        else:
            obj=self.contrato_id

            pagos=self.contrato_id.tabla_amortizacion.filtered(lambda l: l.estado_pago=='pagado')
            pago_capital=sum(pagos.mapped("cuota_capital"))

            nuevoMontoReeestructura=self.monto_financiamiento-pago_capital


            cuotasPagadas=self.contrato_id.tabla_amortizacion.filtered(lambda l: l.estado_pago=='pagado' and l.cuotaAdelantada==False)
            numcuotas_congeladas=self.contrato_id.tabla_amortizacion.filtered(lambda l:  l.cuota_capital == 0)


            cuotasAdelantadas=self.contrato_id.tabla_amortizacion.filtered(lambda l: l.estado_pago=='pagado' and l.cuotaAdelantada==True)


            numeroCuotasPagadaTotal=len(cuotasAdelantadas) + len(cuotasPagadas)


            diferenciaPlazoAdendum= abs(self.contrato_id.plazo_meses.numero - self.plazo_meses.numero)

            numeroCuotasTotal=diferenciaPlazoAdendum

            intervalo_nuevo=self.plazo_meses.numero - numeroCuotasPagadaTotal + len(numcuotas_congeladas)
            
            #lleno lista con estado de cuenta anterior 
            estado_cuenta_anterior=[]
            for e in self.contrato_id.estado_de_cuenta_ids:
                dct ={}
                dct['numero_cuota'] = e.numero_cuota
                dct['fecha']= e.fecha
                dct['cuota_capital']= e.cuota_capital
                dct['cuota_adm']= e.cuota_adm
                dct['iva_adm']= e.iva_adm
                dct['saldo']= e.saldo
                dct['contrato_id']= self.contrato_id.id
                dct['estado_pago']= e.estado_pago
                dct['cuotaAdelantada']= e.cuotaAdelantada
                dct['fecha_pagada']= e.fecha_pagada
                dct['seguro']= e.seguro
                dct['rastreo']= e.rastreo
                dct['factura_id']= e.factura_id.id 
                estado_cuenta_anterior.append(dct)


            porcentaje_perm_adendum =  float(self.env['ir.config_parameter'].sudo().get_param('gzl_adjudicacion.porcentaje_perm_adendum'))
            valor_porcentaje = (self.contrato_id.monto_financiamiento * porcentaje_perm_adendum)/100
            valor_menos_porc = self.contrato_id.monto_financiamiento - valor_porcentaje
            valor_mayor_porc = self.contrato_id.monto_financiamiento + valor_porcentaje
            # el monto de financiamiento nuevo debe ser menos o mas el 30% del monto de financiamiento q ya estaba
            if self.monto_financiamiento >= valor_menos_porc and self.monto_financiamiento <= valor_mayor_porc : 
                #aqui se muestran las cuotas que han sido pagadas ya sean por adelanto o no 
                obj_contrato=self.env['contrato.estado.cuenta'].search([('contrato_id','=',self.contrato_id.id),('estado_pago','=','pagado')])
                lista_cuotapagadas=[]
                cont =0
                monto_finan_contrato= 0.00
                for l in obj_contrato:
                    cont+=1
                    dct ={}
                    dct['numero_cuota'] = cont
                    dct['fecha']= l.fecha
                    dct['cuota_capital']= l.cuota_capital
                    dct['cuota_adm']= l.cuota_adm
                    dct['iva_adm']= l.iva_adm
                    dct['saldo']= l.saldo
                    dct['contrato_id']= self.contrato_id.id
                    dct['estado_pago']= l.estado_pago
                    dct['currency_id']= l.currency_id
                    lista_cuotapagadas.append(dct)


                obj_contrato_detalle=self.env['contrato.estado.cuenta'].search([('contrato_id','=',self.contrato_id.id)])
                obj_contrato_detalle.unlink()


                ####crear cuotas pagadas para listar segun el nuevo plazo o monto
                for a in lista_cuotapagadas:
                    self.env['contrato.estado.cuenta'].create({
                                                        'numero_cuota':a['numero_cuota'],
                                                        'fecha':a['fecha'],
                                                        'cuota_capital':a['cuota_capital'],
                                                        'cuota_adm':a['cuota_adm'],
                                                        'iva_adm':a['iva_adm'],
                                                        'saldo':a['saldo'],
                                                        'contrato_id':a['contrato_id'],
                                                        'estado_pago':a['estado_pago'],                                                
                                                            })
                #crear el nuevo estado de cuenta 
                cuota_capital_nueva = (nuevoMontoReeestructura/int(intervalo_nuevo))
                cuota_capital_nueva =round(cuota_capital_nueva, 2)
                #raise ValidationError(str(cuota_capital_nueva)+'-- cuota_capital_nueva')
                contb=0
                for i in range(cont, int(intervalo_nuevo+cont)):
                    contb +=1
                    cuota_capital = (nuevoMontoReeestructura/int(intervalo_nuevo))
                    cuota_capital =round(cuota_capital, 2)
                    cuota_adm = nuevoMontoReeestructura * self.contrato_id.tasa_administrativa / 100 / 12
                    iva = cuota_adm * 0.12
                    #monto_finan_contrato+= cuota_capital
                    cuota_administrativa_neto= cuota_adm + iva
                    saldo = cuota_capital+cuota_adm+iva
                    self.env['contrato.estado.cuenta'].create({
                                                        'numero_cuota':i+1, 
                                                        'fecha':self.contrato_id.fecha_inicio_pago + relativedelta(months=i),
                                                        'cuota_capital':cuota_capital,
                                                        'cuota_adm':cuota_adm,
                                                        'iva_adm':iva,
                                                        'saldo':saldo,
                                                        'contrato_id':self.contrato_id.id,                                                    
                                                            })
                #si se creo el nuevo estado de cuenta agregar el estado de cuenta anterior a las tablas de bitacora
                obj_estado_cuenta_nuevo=self.env['contrato.estado.cuenta'].search([('contrato_id','=',self.contrato_id.id)])
                if len(obj_estado_cuenta_nuevo) >0:
                    obj_contrato_historico=self.env['contrato.estado.cuenta.historico.cabecera'].create({
                                                        #'numero_cuota':self.contrato_id.numero_cuota,
                                                        'contrato_id':self.contrato_id.id,
                                                        'motivo_adendum':' adendum',
                                                        'cuota_capital':cuota_capital_nueva,
                                                        'monto_financiamiento':self.monto_financiamiento,
                                                        'plazo_meses':self.plazo_meses.id,
                                                        'cuota_capital_anterior':self.contrato_id.cuota_capital,
                                                        'monto_financiamiento_anterior':self.contrato_id.monto_financiamiento,
                                                        'plazo_meses_anterior':self.contrato_id.plazo_meses.id,
                                                        #'currency_id':self.contrato_id.currency_id.id,                                                
                                                            })            


                    ####Crear bitacora detalle de estado de cuenta 
                    obj_estado_cuenta_cabecera=self.env['contrato.estado.cuenta.historico.cabecera'].search([('contrato_id','=',self.contrato_id.id)])
                    if len(obj_estado_cuenta_cabecera) >0:
                        #raise ValidationError(type(obj_estado_cuenta_cabecera.id)+'--obj_estado_cuenta_cabecera.id')
                        for cta_ant in estado_cuenta_anterior:
                            self.env['contrato.estado.cuenta.historico.detalle'].create({
                                                                'numero_cuota':cta_ant['numero_cuota'],
                                                                'fecha':cta_ant['fecha'] ,
                                                                'cuota_capital':cta_ant['cuota_capital'],
                                                                'cuota_adm':cta_ant['cuota_adm'],
                                                                'iva_adm':cta_ant['iva_adm'],
                                                                'saldo':cta_ant['saldo'],
                                                                'estado_pago':cta_ant['estado_pago'], 
                                                                'cuotaAdelantada':cta_ant['cuotaAdelantada'] ,  
                                                                'seguro':cta_ant['seguro'],  
                                                                'fecha_pagada':cta_ant['fecha_pagada'] ,  
                                                                'rastreo':cta_ant['rastreo'],  
                                                                'factura_id':cta_ant['factura_id'] ,#or None,          
                                                                'contrato_id':obj_contrato_historico.id, 
                                                                    })


                ##########################################validar que la cuota capital este bien ####################################################
                monto_finan_contrato = sum(self.contrato_id.tabla_amortizacion.mapped('cuota_capital'))
                monto_finan_contrato = round(monto_finan_contrato,2)
                
                vls=[]
                if  monto_finan_contrato  > self.monto_financiamiento:
                    valor_sobrante = monto_finan_contrato - self.contrato_id.monto_financiamiento 
                    valor_sobrante = round(valor_sobrante,2)
                    parte_decimal, parte_entera = math.modf(valor_sobrante)
                    if parte_decimal >=1:
                        valor_a_restar= (valor_sobrante/parte_decimal)*0.1
                    else:
                        valor_a_restar= (valor_sobrante/parte_decimal)*0.01

                    obj_contrato=self.env['contrato.estado.cuenta'].search([('contrato_id','=',self.contrato_id.id),('estado_pago','=','pendiente')] , order ='fecha desc')
                    for c in obj_contrato:
                        if valor_sobrante != 0.00 or valor_sobrante != 0 or valor_sobrante != 0.0:

                            c.update({
                                'cuota_capital': c.cuota_capital - valor_a_restar,
                                'contrato_id':self.contrato_id.id,
                            })
                            vls.append(valor_sobrante)
                            valor_sobrante = valor_sobrante -valor_a_restar
                            valor_sobrante = round(valor_sobrante,2)
                            
                            
                if  monto_finan_contrato  < self.monto_financiamiento:
                    valor_sobrante = self.contrato_id.monto_financiamiento  - monto_finan_contrato 
                    valor_sobrante = round(valor_sobrante,2)
                    parte_decimal, parte_entera = math.modf(valor_sobrante)
                    if parte_decimal >=1:
                        valor_a_restar= (valor_sobrante/parte_decimal)*0.1
                    else:
                        valor_a_restar= (valor_sobrante/parte_decimal)*0.01

                    obj_contrato=self.env['contrato.estado.cuenta'].search([('contrato_id','=',self.contrato_id.id),('estado_pago','=','pendiente')] , order ='fecha desc')

                    for c in obj_contrato:

                        if valor_sobrante != 0.00 or valor_sobrante != 0 or valor_sobrante != 0.0:
                            #raise ValidationError(str(valor_sobrante)+'--'+str(parte_decimal)+'----'+str(valor_a_restar))
                            c.update({
                                'cuota_capital': c.cuota_capital + valor_a_restar,
                                'contrato_id':self.contrato_id.id,
                            })  
                            vls.append(valor_sobrante)
                            valor_sobrante = valor_sobrante -valor_a_restar
                            valor_sobrante = round(valor_sobrante,2)
                ##si esta ejecutado se ocultara el boton de validar                  
                self.ejecutado =True
                #asignar nuevos valores 
                self.contrato_id.monto_financiamiento = self.monto_financiamiento
                self.contrato_id.plazo_meses =self.plazo_meses.id
                self.contrato_id.cuota_capital=cuota_capital_nueva
                self.contrato_id.ejecutado = True
                self.env['contrato.adendum'].create({
                                'contrato_id': self.contrato_id.id,
                                'socio_id':self.socio_id.id,
                                'monto_financiamiento':self.monto_financiamiento,
                                'plazo_meses':self.plazo_meses.id,
                                'observacion':self.observacion,
                                #'currency_id':self.contrato_id.id,
                            })  

            else:
                raise ValidationError("El monto de financiamiento no esta en el rango permitido")