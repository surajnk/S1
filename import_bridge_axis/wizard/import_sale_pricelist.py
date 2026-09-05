# -*- coding: utf-8 -*-
#################################################################################
# Author      : AxisTechnolabs.com
# Copyright(c): 2011-Axistechnolabs.com.
# All Rights Reserved.
#
# This program is copyright property of the author mentioned above.
# You can`t redistribute it and/or modify it.
#
#################################################################################
from odoo import models, fields, _,api
from odoo.exceptions import Warning
from odoo.exceptions import UserError
import logging
import tempfile
import binascii
import datetime

_logger = logging.getLogger(__name__)
import io
import re

try:
    import csv
except ImportError:
    _logger.debug('Cannot `import csv`.')
try:
    import xlrd
except ImportError:
    _logger.debug('Cannot `import Excel`.')
try:
    import base64
except ImportError:
    _logger.debug('Cannot `import base64`.')


class ImportClient(models.TransientModel):
    _name = "import.sale.pricelist"
    _description = 'import sale pricelist'

    import_file = fields.Binary(string="Add File")
    file_option = fields.Selection([('csv', 'CSV File'), ('xls', 'XLS File')], string='Select File', default='csv')

    def import_sale_pricelist(self):

        if self.file_option != 'csv':
            raise UserError(_("Only CSV is supported."))
        if not self.import_file:
            raise UserError(_("Please attach a CSV file."))

        raw = base64.b64decode(self.import_file)
        decoded = raw.decode('utf-8', errors='ignore')

        # Auto-detect delimiter
        sniffed_delim = ','
        try:
            sample = decoded[:4096]
            dialect = csv.Sniffer().sniff(sample, delimiters=[',', ';', '|', '\t'])
            sniffed_delim = dialect.delimiter or ','
        except Exception:
            if '|' in decoded and ',' not in decoded:
                sniffed_delim = '|'

        buf = io.StringIO(decoded)
        reader = csv.DictReader(buf, delimiter=sniffed_delim)

        if not reader.fieldnames:
            raise UserError(_("No headers found in CSV."))

        # ---- normalize & resolve headers ----
        def norm(s): return re.sub(r'[^a-z0-9]+', '', (s or '').lower())
        actual_by_norm = {norm(h): h for h in reader.fieldnames}

        def col(*aliases):
            for a in aliases:
                h = actual_by_norm.get(norm(a))
                if h:
                    return h
            return None

        # Core columns
        C_PL      = col('Pricelist Name','name')
        C_CUR     = col('Currency_id','Currency')
        C_APPLY   = col('Pricelist Items/Apply On','Apply On')
        C_PR_CODE = col('Pricelist Items/Pricing Code','Pricing Code')
        C_COMP    = col('Pricelist Items/Compute Price','Compute Price')
        C_FIX     = col('Pricelist Items/Fixed Price','Fixed Price')
        C_PCT     = col('Pricelist Items/Percentage Price','Percentage Price')
        C_PG      = col('Pricelist Items/Price Group','Price Group')
        C_COMC    = col('Pricelist Items/Product Commodity Code','Product Commodity Code')
        C_IG      = col('Pricelist Items/Item Group','Item Group')
        C_PROD    = col('Pricelist Items/Product','Product')
        C_LAB     = col('Pricelist Items/Labor Item','Labor Item')
        C_BRK     = col('Pricelist Items/Quantity Break Code','Quantity Break Code')
        C_MINQ    = col('Pricelist Items/Min. Quantity','Min. Quantity','Min Quantity')
        C_START   = col('Start Date')
        C_END     = col('End Date')
        C_CAT     = col('Pricelist Items/Product Category','Product Category')
        C_UNIT    = col('Pricelist Items/Unit Type')
        C_IMPL    = col('Implement Change')

        # Quantity Breaks (tolerant aliases)
        C_QB_QTY         = col('Pricelist Items/Quantity Breaks/Quantity Breaks','Quantity Breaks','Qty Breaks','Range','Quantity Breaks/Quantity Breaks')
        C_QB_DISC        = col('Pricelist Items/Quantity Breaks/Discount','Break Discount','Discount')
        C_QB_FIX         = col('Pricelist Items/Quantity Breaks/Fixed Price','Break Fixed Price','Fixed Price (Break)','Fixed Price')
        C_QB_LEVEL_PRICE = col('Pricelist Items/Quantity Breaks/Level Price','Level Price')
        C_QB_LEVEL_NAME  = col('Pricelist Items/Quantity Breaks/Level','Level')

        # Cust Unit Breaks (optional)
        C_CUST_QTY   = col('Pricelist Items/Cust Unit Breaks/Cust Qty Breaks','Cust Qty Breaks')
        C_CUST_PRICE = col('Pricelist Items/Cust Unit Breaks/Cust Unit Price','Cust Unit Price')

        # helpers
        def s2(v):  return (v or '').strip()
        def f2(v, d=0.0):
            try:
                return float(str(v).replace(',', '').strip()) if v not in (None, '') else d
            except Exception:
                return d
        def d2(v):
            if not v:
                return False
            for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%d/%m/%Y"):
                try:
                    return datetime.datetime.strptime(str(v).strip(), fmt).date()
                except Exception:
                    pass
            raise UserError(_("Invalid date '%s'.") % v)

        # env shortcuts
        Pricelist   = self.env['product.pricelist']
        Item        = self.env['product.pricelist.item']
        Product     = self.env['product.product']
        ProductTmpl = self.env['product.template']
        Category    = self.env['product.category']
        PriceGroup  = self.env['price.group']
        ItemGroup   = self.env['product.item.group']
        LaborItem   = self.env['labor.items']
        Commodity   = self.env['product.commodity.code']
        Currency    = self.env['res.currency']
        BreakCodes  = self.env['product.break.codes']

        # caches
        c_pl, c_cur, c_tmpl, c_prod, c_cat, c_pg, c_ig, c_li, c_cc, c_bc = ({} for _ in range(10))

        def get_cur(code):
            if not code:
                return False
            if code not in c_cur:
                c_cur[code] = Currency.search([('name', '=', code)], limit=1)
            return c_cur[code].id if c_cur[code] else False

        def get_bc(name):
            if not name:
                return False
            if name not in c_bc:
                c_bc[name] = BreakCodes.search([('name', '=', name)], limit=1)
            return c_bc[name].id if c_bc[name] else False

        APPLY_ON = {
            'commodity group': '7_commodity_group',
            'price group':     '6_price_group',
            'labor item':      '5_labor_item',
            'item group':      '4_item_group',
            'all products':    '3_global',
            'product category':'2_product_category',
            'product':         '1_product',
            'product variant': '0_product_variant',
        }

        created = 0
        touched = set()

        # state
        current_pl = False
        current_item = False
        pending_breaks = []
        pending_cust_breaks = []

        # ---------- classification & grouping ----------
        def _has_any(row, cols):
            return any(cols) and any(s2(row.get(k)) for k in cols if k)

        BREAK_COLS = [C_QB_QTY, C_QB_DISC, C_QB_FIX, C_QB_LEVEL_PRICE, C_QB_LEVEL_NAME, C_CUST_QTY, C_CUST_PRICE]
        ITEM_CORE_COLS = [
            C_PL, C_APPLY, C_PR_CODE, C_COMP, C_FIX, C_PCT, C_MINQ, C_START, C_END, C_BRK, C_UNIT, C_IMPL,
            C_PG, C_COMC, C_IG, C_PROD, C_LAB, C_CAT,
        ]

        def is_break_row(r): return _has_any(r, BREAK_COLS)
        def is_item_row(r):  return _has_any(r, ITEM_CORE_COLS)

        # Identity should only include the stable “target” of pricing + pricelist context.
        IDENTITY_COLS = [
            C_PL, C_APPLY, C_PR_CODE, C_COMP,  # DO NOT include fixed/percent amounts that may vary
            C_PROD, C_CAT, C_PG, C_COMC, C_IG, C_LAB,  # target discriminators
            C_BRK,  # optional grouping by break code
        ]
        def make_key(r):
            return '|'.join((s2(r.get(c)).lower() if c else '') for c in IDENTITY_COLS)

        # Target-only key (even looser) to keep appending when someone repeats header-ish cells on break rows
        TARGET_ONLY_COLS = [C_APPLY, C_PROD, C_CAT, C_PG, C_COMC, C_IG, C_LAB, C_BRK]
        def make_target_key(r):
            return '|'.join((s2(r.get(c)).lower() if c else '') for c in TARGET_ONLY_COLS)

        prev_key = None
        prev_target_key = None

        # write collected breaks to item
        def flush_break_overrides():
            nonlocal pending_breaks, pending_cust_breaks, current_item
            if not current_item or (not pending_breaks and not pending_cust_breaks):
                pending_breaks = []
                pending_cust_breaks = []
                return

            cmds_breaks = []
            for br in pending_breaks:
                line_vals = {'x_product_qty_pr': br.get('qty') or ''}
                if br.get('disc') not in (None, ''):
                    line_vals['x_product_discount_on_level_pr'] = f2(br['disc'])
                if br.get('fix') not in (None, ''):
                    line_vals['x_product_price_per_value_pr'] = f2(br['fix'])
                if br.get('levelprice') not in (None, ''):
                    line_vals['x_product_level_price_pr'] = f2(br['levelprice'])
                if br.get('levelname'):
                    line_vals['x_product_lvl_pr'] = br['levelname']
                cmds_breaks.append((0, 0, line_vals))

            cmds_cust = []
            for br in pending_cust_breaks:
                line_vals = {'x_product_cust_qty_pr': br.get('qty') or ''}
                if br.get('price') not in (None, ''):
                    line_vals['x_product_cust_unit_price'] = f2(br['price'])
                cmds_cust.append((0, 0, line_vals))

            write_vals = {}
            if cmds_breaks:
                write_vals['x_pricelist_break_qty_price'] = [(5, 0, 0)] + cmds_breaks
            if cmds_cust:
                write_vals['x_pricelist_break_cust_qty_price'] = [(5, 0, 0)] + cmds_cust

            if write_vals:
                current_item.write(write_vals)

            pending_breaks = []
            pending_cust_breaks = []

        # -------------------- MAIN LOOP --------------------
        for i, row in enumerate(reader, start=2):
            # ignore completely empty lines
            if not any(s2(v) for v in row.values()):
                continue

            row_key = make_key(row)
            row_target = make_target_key(row)

            if is_item_row(row):
                # If the row has ANY break data and the target identity didn't change,
                # treat it as a continuation row (append more breaks) — DO NOT create a new item.
                if current_item and is_break_row(row) and prev_target_key and row_target == prev_target_key:
                    if _has_any(row, [C_QB_QTY, C_QB_DISC, C_QB_FIX, C_QB_LEVEL_PRICE, C_QB_LEVEL_NAME]):
                        pending_breaks.append({
                            'qty':        s2(row.get(C_QB_QTY))         if C_QB_QTY else '',
                            'disc':       s2(row.get(C_QB_DISC))        if C_QB_DISC else '',
                            'fix':        s2(row.get(C_QB_FIX))         if C_QB_FIX else '',
                            'levelprice': s2(row.get(C_QB_LEVEL_PRICE)) if C_QB_LEVEL_PRICE else '',
                            'levelname':  s2(row.get(C_QB_LEVEL_NAME))  if C_QB_LEVEL_NAME else '',
                        })
                    if (C_CUST_QTY and s2(row.get(C_CUST_QTY))) or (C_CUST_PRICE and s2(row.get(C_CUST_PRICE))):
                        pending_cust_breaks.append({
                            'qty':   s2(row.get(C_CUST_QTY))   if C_CUST_QTY else '',
                            'price': s2(row.get(C_CUST_PRICE)) if C_CUST_PRICE else '',
                        })
                    continue  # skip creating a fresh item

                # New group → flush previous
                flush_break_overrides()
                prev_key = row_key
                prev_target_key = row_target

                # resolve pricelist (carry-forward if blank)
                pl_name_cell = s2(row.get(C_PL)) if C_PL else ''
                if pl_name_cell:
                    pl = c_pl.get(pl_name_cell)
                    if not pl:
                        vals_pl = {'name': pl_name_cell}
                        cur_code = s2(row.get(C_CUR)) if C_CUR else ''
                        cid = get_cur(cur_code)
                        if cid:
                            vals_pl['currency_id'] = cid
                        pl = Pricelist.search([('name', '=', pl_name_cell)], limit=1) or Pricelist.create(vals_pl)
                        c_pl[pl_name_cell] = pl
                    current_pl = pl
                else:
                    if not current_pl:
                        raise UserError(_("Row %d: Missing '%s' and no previous pricelist context.") % (i, C_PL))
                    pl = current_pl

                touched.add(pl.id)

                apply_txt = s2(row.get(C_APPLY)) if C_APPLY else 'All Products'
                applied_on = APPLY_ON.get(apply_txt.lower(), '3_global')

                compute = (s2(row.get(C_COMP)) if C_COMP else 'Fixed Price').lower()
                vals = {
                    'pricelist_id': pl.id,
                    'applied_on': applied_on,
                    'compute_price': 'fixed' if compute.startswith('fixed') else 'percentage',
                    'fixed_price': f2(row.get(C_FIX)) if C_FIX else 0.0,
                    'percent_price': f2(row.get(C_PCT)) if C_PCT else 0.0,
                    'min_quantity': f2(row.get(C_MINQ)) if C_MINQ else 0.0,
                    'date_start': d2(row.get(C_START)) if C_START else False,
                    'date_end':   d2(row.get(C_END))   if C_END   else False,
                    'x_pricelist_pricing_code': s2(row.get(C_PR_CODE)) if C_PR_CODE else False,
                }

                unit = s2(row.get(C_UNIT)).lower() if C_UNIT else ''
                if 'master' in unit:
                    vals['use_cust_units'] = 'master_yards'
                elif unit:
                    vals['use_cust_units'] = 'customer_units'

                impl = s2(row.get(C_IMPL)).lower() if C_IMPL else ''
                if impl == 'current':
                    vals['x_pricelist_implement'] = 'current'

                # target per Apply On
                if applied_on == '1_product':
                    name = s2(row.get(C_PROD)) if C_PROD else ''
                    if not name:
                        raise UserError(_("Row %d: Product required.") % i)
                    if name not in c_tmpl:
                        rec = ProductTmpl.search([('name', '=', name)], limit=1) or ProductTmpl.create({'name': name})
                        c_tmpl[name] = rec
                    vals['product_tmpl_id'] = c_tmpl[name].id

                elif applied_on == '0_product_variant':
                    name = s2(row.get(C_PROD)) if C_PROD else ''
                    if not name:
                        raise UserError(_("Row %d: Variant required.") % i)
                    if name not in c_prod:
                        rec = Product.search([('name', '=', name)], limit=1) or Product.create({'name': name})
                        c_prod[name] = rec
                    vals['product_id'] = c_prod[name].id

                elif applied_on == '2_product_category':
                    cname = s2(row.get(C_CAT)) if C_CAT else ''
                    if not cname:
                        raise UserError(_("Row %d: Category required.") % i)
                    if cname not in c_cat:
                        rec = Category.search([('name', '=', cname)], limit=1) or Category.create({'name': cname})
                        c_cat[cname] = rec
                    vals['categ_id'] = c_cat[cname].id

                elif applied_on == '4_item_group':
                    g = s2(row.get(C_IG)) if C_IG else ''
                    if not g:
                        raise UserError(_("Row %d: Item Group required.") % i)
                    if g not in c_ig:
                        rec = ItemGroup.search([('name', '=', g)], limit=1) or ItemGroup.create({'name': g})
                        c_ig[g] = rec
                    vals['product_item_group_id'] = c_ig[g].id

                elif applied_on == '5_labor_item':
                    l = s2(row.get(C_LAB)) if C_LAB else ''
                    if not l:
                        raise UserError(_("Row %d: Labor Item required.") % i)
                    if l not in c_li:
                        rec = LaborItem.search([('name', '=', l)], limit=1) or LaborItem.create({'name': l})
                        c_li[l] = rec
                    vals['labor_item_id'] = c_li[l].id

                elif applied_on == '6_price_group':
                    pg_val = s2(row.get(C_PG))
                    if not pg_val:
                        raise UserError(_("Row %d: Price Group required.") % i)
                    pg_rec = c_pg.get(pg_val)
                    if not pg_rec:
                        PG = self.env['price.group']
                        pg_rec = PG.search([('x_pricegroup', '=', pg_val)], limit=1) or \
                                 PG.search([('x_pricegroup', '=ilike', pg_val)], limit=1)
                        if not pg_rec:
                            pg_rec = PG.create({'x_pricegroup': pg_val})
                        c_pg[pg_val] = pg_rec
                    vals['price_group_id'] = pg_rec.id

                elif applied_on == '7_commodity_group':
                    cc = s2(row.get(C_COMC)) if C_COMC else ''
                    if not cc:
                        raise UserError(_("Row %d: Commodity Code required.") % i)
                    if cc not in c_cc:
                        rec = Commodity.search([('name', '=', cc)], limit=1) or Commodity.create({'name': cc})
                        c_cc[cc] = rec
                    vals['product_commodity_id'] = c_cc[cc].id

                bc = s2(row.get(C_BRK)) if C_BRK else ''
                if bc:
                    bid = get_bc(bc)
                    if bid:
                        vals['x_pricelist_break_code'] = bid

                # create the item
                current_item = Item.create(vals)
                created += 1
                pending_breaks = []
                pending_cust_breaks = []

                # seed breaks from the same row if present
                if _has_any(row, [C_QB_QTY, C_QB_DISC, C_QB_FIX, C_QB_LEVEL_PRICE, C_QB_LEVEL_NAME]):
                    pending_breaks.append({
                        'qty':        s2(row.get(C_QB_QTY))         if C_QB_QTY else '',
                        'disc':       s2(row.get(C_QB_DISC))        if C_QB_DISC else '',
                        'fix':        s2(row.get(C_QB_FIX))         if C_QB_FIX else '',
                        'levelprice': s2(row.get(C_QB_LEVEL_PRICE)) if C_QB_LEVEL_PRICE else '',
                        'levelname':  s2(row.get(C_QB_LEVEL_NAME))  if C_QB_LEVEL_NAME else '',
                    })
                if (C_CUST_QTY and s2(row.get(C_CUST_QTY))) or (C_CUST_PRICE and s2(row.get(C_CUST_PRICE))):
                    pending_cust_breaks.append({
                        'qty':   s2(row.get(C_CUST_QTY))   if C_CUST_QTY else '',
                        'price': s2(row.get(C_CUST_PRICE)) if C_CUST_PRICE else '',
                    })

            elif is_break_row(row):
                # additional breaks for current item
                if not current_item:
                    continue
                if _has_any(row, [C_QB_QTY, C_QB_DISC, C_QB_FIX, C_QB_LEVEL_PRICE, C_QB_LEVEL_NAME]):
                    pending_breaks.append({
                        'qty':        s2(row.get(C_QB_QTY))         if C_QB_QTY else '',
                        'disc':       s2(row.get(C_QB_DISC))        if C_QB_DISC else '',
                        'fix':        s2(row.get(C_QB_FIX))         if C_QB_FIX else '',
                        'levelprice': s2(row.get(C_QB_LEVEL_PRICE)) if C_QB_LEVEL_PRICE else '',
                        'levelname':  s2(row.get(C_QB_LEVEL_NAME))  if C_QB_LEVEL_NAME else '',
                    })
                if (C_CUST_QTY and s2(row.get(C_CUST_QTY))) or (C_CUST_PRICE and s2(row.get(C_CUST_PRICE))):
                    pending_cust_breaks.append({
                        'qty':   s2(row.get(C_CUST_QTY))   if C_CUST_QTY else '',
                        'price': s2(row.get(C_CUST_PRICE)) if C_CUST_PRICE else '',
                    })
            else:
                continue

        # flush last
        flush_break_overrides()

        if created == 0:
            _logger.info("Pricelist import: 0 items. Headers: %s", reader.fieldnames)
            raise UserError(_("No valid header rows found. Check column captions."))

        # optional debug (you can keep/remove)
        _logger.info("Pricelist import: Created %s item(s).", created)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Pricelist import complete"),
                'message': _("Created %s item(s).") % created,
                'sticky': False,
            }
        }


    
    # def import_sale_pricelist(self):
    #     if self.file_option == 'csv':
            
    #         csv_data = base64.b64decode(self.import_file)
    #         data_file = io.StringIO(csv_data.decode("utf-8"))
    #         data_file.seek(0)
    #         csv_reader = csv.DictReader(data_file, delimiter=',')
           

    #         partner = self.env['res.partner']
    #         product_name = self.env['product.product']
    #         product = self.env['product.template']
    #         lst =[]
           

    #         for line in csv_reader:
               

    #             if line.get('Product Template'):
    #                 product = product.search([('name', '=', line.get('Product Template'))])
    #                 if not product:
    #                     product = product.create({
    #                         'name': line.get('Product Template'),
    #                     })
    #                 partner_count = product.sudo().search_count([('name', '=', line.get('Product Template'))])
    #                 lst.append(partner_count)


    #             if line.get('Product Variant'):
    #                 product_name = product_name.search([('name', '=', line.get('Product Variant'))])
    #                 if not product_name:
    #                     product_name = product_name.create({
    #                         'name': line.get('Product Variant'),
    #                     })



    #             if line.get('Start Date'):
    #                 start_date = datetime.datetime.strptime(line['Start Date'], '%m/%d/%Y')
    #             else:
    #                 start_date = datetime.datetime.now()

    #             if line.get('End Date'):
    #                 end_date = datetime.datetime.strptime(line['End Date'], '%m/%d/%Y')
    #             else:
    #                 end_date = datetime.datetime.now()

            
    #             product_pricelist_info = self.env['product.pricelist'].create({
    #                 'name': line.get('Pricelist Name'),
    #                 'item_ids':
    #                     [(0, 0, {
    #                              'min_quantity': line.get('MIn Qty'),
    #                              'fixed_price': line.get('Amount'),
    #                              'date_end': end_date,
    #                              'date_start':start_date,
    #                              'product_tmpl_id':product.id,
    #                              'product_id':product_name.id,
    #                              })],

    #             })

    #         get_count=0
    #         for rec in lst:
    #             get_count = get_count+rec
                
    #         model = self.env.context.get('active_model')
    #         if model == 'custom.dashboard':
    #            vendor_info = self.env['custom.dashboard'].sudo().search([['name','=','Sale Pricelist']])
    #            if vendor_info.count == 0:
    #               vendor_info.count = get_count
    #            else:
    #               vendor_info.count += get_count


    #     elif self.file_option == 'xls':
    #         fp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
    #         fp.write(binascii.a2b_base64(self.import_file))
    #         fp.seek(0)
    #         workbook = xlrd.open_workbook(fp.name)
    #         sheet = workbook.sheet_by_index(0)
    #         keys = sheet.row_values(0)
    #         xls_reader = [sheet.row_values(i) for i in range(1, sheet.nrows)]
           

    #         partner = self.env['res.partner']
    #         product_name = self.env['product.product']
    #         product = self.env['product.template']
    #         lst =[]
           

    #         for row in xls_reader:
    #             line = dict(zip(keys, row))

    #             if line.get('Product Template'):
    #                 product = product.search([('name', '=', line.get('Product Template'))])
    #                 if not product:
    #                     product = product.create({
    #                         'name': line.get('Product Template'),
    #                     })
    #                 partner_count = product.sudo().search_count([('name', '=', line.get('Product Template'))])
    #                 lst.append(partner_count)

    #             if line.get('Product Variant'):
    #                 product_name = product_name.search([('name', '=', line.get('Product Variant'))])
    #                 if not product_name:
    #                     product_name = product_name.create({
    #                         'name': line.get('Product Variant'),
    #                     })

    #             if line.get('Start Date'):
    #                  start_date = xlrd.xldate.xldate_as_datetime(line['Start Date'], workbook.datemode)
    #             else:
    #                 start_date = datetime.datetime.now()

    #             if line.get('End Date'):
    #                  end_date = xlrd.xldate.xldate_as_datetime(line['End Date'], workbook.datemode)    
    #             else:
    #                 end_date = datetime.datetime.now()

            
    #             product_pricelist_info = self.env['product.pricelist'].create({
    #                 'name': line.get('Pricelist Name'),
    #                 'item_ids':
    #                     [(0, 0, {'min_quantity': line.get('MIn Qty'),
    #                              'fixed_price': line.get('Amount'),
    #                              'date_end': end_date,
    #                              'date_start':start_date,
    #                              'product_tmpl_id':product.id,
    #                              'product_id':product_name.id,
    #                              })],

    #             })
    #         get_count=0
    #         for rec in lst:
    #             get_count = get_count+rec
                
    #         model = self.env.context.get('active_model')
    #         if model == 'custom.dashboard':
    #            vendor_info = self.env['custom.dashboard'].sudo().search([['name','=','Sale Pricelist']])
    #            if vendor_info.count == 0:
    #               vendor_info.count = get_count
    #            else:
    #               vendor_info.count += get_count

    #     else:
    #         raise Warning(_("Invalid file!"))


    #  