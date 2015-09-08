# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2015 Deltatech All Rights Reserved
#                    Dorin Hongu <dhongu(@)gmail(.)com       
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#
##############################################################################


from openerp import models, fields, api, _
from openerp.exceptions import except_orm, Warning, RedirectWarning
from openerp.tools import float_compare
import openerp.addons.decimal_precision as dp
import math
from openerp.osv.fields import related


def ean_checksum(eancode):
    """returns the checksum of an ean string of length 13, returns -1 if the string has the wrong length"""
    if len(eancode) != 13:
        return -1
    oddsum=0
    evensum=0
    total=0
    eanvalue=eancode
    reversevalue = eanvalue[::-1]
    finalean=reversevalue[1:]

    for i in range(len(finalean)):
        if i % 2 == 0:
            oddsum += int(finalean[i])
        else:
            evensum += int(finalean[i])
    total=(oddsum * 3) + evensum

    check = int(10 - math.ceil(total % 10.0)) %10
    return check

def check_ean(eancode):
    """returns True if eancode is a valid ean13 string, or null"""
    if not eancode:
        return True
    if len(eancode) != 13:
        return False
    try:
        int(eancode)
    except:
        return False
    return ean_checksum(eancode) == int(eancode[-1])





class service_equipment(models.Model):
    _name = 'service.equipment'
    _description = "Equipment"
    _inherit = 'mail.thread'

    agreement_id = fields.Many2one('service.agreement', string='Contract Services', compute="_compute_agreement_id")
    partner_id = fields.Many2one('res.partner', string='Partner', compute="_compute_agreement_id")
    user_id = fields.Many2one('res.users', string='Responsible', track_visibility='onchange')
        
    # unde este echipamentul
    address_id = fields.Many2one('res.partner', string='Location',  required=True,  track_visibility='onchange') 
    work_location = fields.Char(string='Work Location')
    contact_id = fields.Many2one('res.partner', string='Contact person',  track_visibility='onchange')    

    name = fields.Char(string='Name', index=True, default="/" )
    product_id = fields.Many2one('product.product', string='Product', ondelete='restrict', domain=[('type', '=', 'product')] )
    serial_id = fields.Many2one('stock.production.lot', string='Serial Number', ondelete="restrict")
    quant_id = fields.Many2one('stock.quant', string='Quant', ondelete="restrict")

    
    note =  fields.Text(String='Notes') 
    start_date = fields.Date(string='Start Date') 

    meter_ids = fields.One2many('service.meter', 'equipment_id', string='Meters' )     
    meter_reading_ids = fields.One2many('service.meter.reading', 'equipment_id', string='Meter Reading') # mai trebuie ??
    state = fields.Selection([  ('online','Online'), ('offline','Offline'), ], string='Status')
    ean_code = fields.Char(string="EAN Code")

    vendor_id = fields.Many2one('res.partner', string='Vendor')
    manufacturer_id = fields.Many2one('res.partner', string='Manufacturer')
 
    image_qr_html = fields.Html(string="QR image", compute="_compute_image_qr_html")
    type_id = fields.Many2one('service.equipment.type', string='Type')

 

    plan_ids = fields.One2many('service.plan', 'equipment_id', string='Plans' ) 
    
    # canda a fost facuta ultima revizie ? si trebuie putin modificata
    last_call_done  = fields.Date(string="Last call done", compute="_compute_last_call_done")


    consumable_id =  fields.Many2one('service.consumable', string='Consumable List')
    
    consumable_item_ids =  fields.Many2many('service.consumable.item', string='Consumables', compute="_compute_consumable_item_ids", readonly=True)

    _sql_constraints = [
        ('ean_code_uniq', 'unique(ean_code)',
            'EAN Code already exist!'),
    ]  
    
    @api.one
    def _compute_consumable_item_ids(self):
        self.consumable_item_ids = self.env['service.consumable.item'].search([('consumable_id','=',self.consumable_id.id)])
    
    @api.one
    def _compute_image_qr_html(self):
        self.image_qr_html = "<img src='/report/barcode/?type=%s&value=%s&width=%s&height=%s'/>" %   ('QR', self.ean_code or '', 150, 150)
        
        
    @api.one
    def _compute_last_call_done(self):
        plans = self.env['service.plan'].search([('equipment_id','=',self.id),('state','=','active')])
        if plans:
            calls = self.env['service.plan.call'].search([('plan_id','in',plans.ids),('state','=','completion')],order='completion_date DESC', limit=1)
            if calls:
                self.last_call_done = calls.completion_date
        

    @api.one
    def _compute_agreement_id(self):
        if not isinstance(self.id, models.NewId):
            agreements = self.env['service.agreement']
            agreement_line = self.env['service.agreement.line'].search([('equipment_id','=',self.id)])
            for line in agreement_line:
                agreements = agreements | line.agreement_id  
            if len(agreements) > 1:
                msg = _("Equipment %s assigned to many agreements." )
                self.post_message(msg)
            if len(agreements) > 0:
                self.agreement_id =  agreements[0]
                self.partner_id = agreements[0].partner_id
    
    
    @api.onchange('product_id','partner_id')
    def onchange_product_id(self):
        if self.name == '':
            if self.product_id:
                self.name = self.product_id.name 
            else:
                self.name = ''
            if self.partner_id: 
                self.name += ', ' + self.partner_id.name  
        if self.product_id:
            self.consumable_id =  self.env['service.consumable'].search([('product_id','=',self.product_id.id)])


    
    @api.multi
    def invoice_button(self):
        invoices = self.env['account.invoice']
        for meter_reading in self.meter_reading_ids:
            if meter_reading.consumption_id and meter_reading.consumption_id.invoice_id:
                invoices = invoices | meter_reading.consumption_id.invoice_id
        
        return {
            'domain': "[('id','in', ["+','.join(map(str,invoices.ids))+"])]",
            'name': _('Services Invoices'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'account.invoice',
            'view_id': False,
            'context': "{'type':'out_invoice', 'journal_type': 'sale'}",
            'type': 'ir.actions.act_window'
        }







    @api.multi
    def notification_button(self):
        notifications = self.env['service.notification'].search([('equipment_id','in',self.ids)])
        context = {
                    'default_equipment_id':self.id,
                    'default_partner_id':self.partner_id.id,
                    'default_agreement_id':self.agreement_id.id,
                    'default_address_id':self.address_id.id,
                    'default_contact_id':self.contact_id.id,
                   }    
        return {
            'domain': "[('id','in', ["+','.join(map(str,notifications.ids))+"])]",
            'name': _('Notifications'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'service.notification',
            'view_id': False,
            'context': context,
            'type': 'ir.actions.act_window'
        }       


    @api.multi
    def order_button(self):
        orders = self.env['service.order'].search([('equipment_id','in',self.ids)])
        context = {
                    'default_equipment_id':self.id,
                    'default_partner_id':self.partner_id.id,
                    'default_agreement_id':self.agreement_id.id,
                    'default_address_id':self.address_id.id,
                    'default_contact_id':self.contact_id.id,
                   }     
        return {
            'domain': "[('id','in', ["+','.join(map(str,orders.ids))+"])]",
            'name': _('Orders'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'service.order',
            'view_id': False,
            'context': context,
            'type': 'ir.actions.act_window'
        }  

    @api.multi
    def picking_button(self):
        pickings = self.env['stock.picking'].search([('equipment_id','in',self.ids)])
        context = {'default_equipment_id':self.id,
                   'default_agreement_id':self.agreement_id.id,
                   'default_picking_type_code':'outgoing',
                   'default_picking_type_id': self.env.ref('stock.picking_type_outgoing_not2binvoiced').id,
                   'default_partner_id':self.address_id.id}     
 
        return {
            'domain': "[('id','in', ["+','.join(map(str,pickings.ids))+"])]",
            'name': _('Delivery for service'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'stock.picking',
            'view_id': False,
            'context': context,
            'type': 'ir.actions.act_window'
        }       

    @api.multi
    def new_piking_button(self):
        
        # todo: de pus in config daca livrarea se face la adresa din echipamente sau contract
        context = {'default_equipment_id':self.id,
                   'default_agreement_id':self.agreement_id.id,
                   'default_picking_type_code':'outgoing',
                   'default_picking_type_id': self.env.ref('stock.picking_type_outgoing_not2binvoiced').id,
                   'default_partner_id':self.address_id.id}
        if self.consumable_item_ids:
            
            picking = self.env['stock.picking'].with_context(context)
            
            context['default_move_lines'] = []
           
            for item in self.consumable_item_ids:                
                value = picking.move_lines.onchange_product_id(prod_id=item.product_id.id)['value']
                value['location_id'] =  picking.move_lines._default_location_source()
                value['location_dest_id'] =  picking.move_lines._default_location_destination()
                value['date_expected'] = fields.Datetime.now()
                value['product_id'] = item.product_id.id
                context['default_move_lines'] += [(0,0,value)]
        return {
            'name': _('Delivery for service'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'stock.picking',
            'view_id': False,
            'views': [[False, 'form']],
            'context': context,
            'type': 'ir.actions.act_window'
        }        



    @api.one
    @api.constrains('ean_code')
    @api.onchange('ean_code')
    def _check_ean_key(self):
        if not check_ean(self.ean_code):
            raise Warning(_('Error: Invalid EAN code'))
        


class service_equipment_type(models.Model):
    _name = 'service.equipment.type'
    _description = "Service Equipment Type"     
    name = fields.Char(string='Type', translate=True)  
    

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: