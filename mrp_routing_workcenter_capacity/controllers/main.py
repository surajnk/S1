from odoo import http
from odoo.http import request, Response

class ZplLabelController(http.Controller):

    @http.route('/mrp/roll_label_zpl/<int:roll_line_id>', 
                type='http', auth='user')
    def print_zpl_label(self, roll_line_id, **kwargs):
        roll_line = request.env['mrp.wo.roll.line'].browse(roll_line_id)
        if not roll_line.exists():
            return Response('Not found', status=404)

        wo = roll_line.workorder_id
        data = wo.get_productivity_label_data(roll_line, wo)

        zpl = self._build_zpl(roll_line, data)

        return Response(
            zpl,
            headers={
                'Content-Type': 'application/octet-stream',
                'Content-Disposition': f'attachment; filename=roll_{roll_line_id}.zpl',
            }
        )

    def _build_zpl(self, roll_line, data):
        roll_name = roll_line.roll_id.name or ''
        item = data.get('item') or ''
        name_01 = data.get('name_01') or ''
        customer_width = str(int(data.get('customer_width') or 0))
        customer_ref = data.get('customer_ref') or ''
        so_date = str(data.get('so_expected_date') or '')
        total_yards = str(data.get('total_yards') or 0)

        # Build detail rows
        row_zpl = ''
        y = 480
        for machine_block in data.get('data_lines', []):
            machine = machine_block.get('machine', '')
            for line in machine_block.get('lines', []):
                operator = line.get('operator') or ''
                date = line.get('date') or ''
                yards = str(line.get('yards') or '')
                row_zpl += (
                    f'^FO10,{y}^A0N,18,18^FD{machine}^FS'
                    f'^FO120,{y}^A0N,18,18^FD{operator}^FS'
                    f'^FO230,{y}^A0N,18,18^FD{date}^FS'
                    f'^FO480,{y}^A0N,18,18^FD{yards}^FS'
                )
                y += 25

        zpl = f"""^XA
^PW812
^LL1218
^CI28

^FO10,10^A0N,40,40^FD{roll_name}^FS
^FO10,55^A0N,30,30^FD{item}^FS

^FO10,100^BCN,80,Y,N,N^FD{roll_name}^FS

^FO10,210^A0N,36,36^FD{name_01}^FS

^FO10,260^A0N,36,36^FD{customer_width}"^FS
^FO200,260^A0N,36,36^FD{customer_ref}^FS
^FO420,260^A0N,36,36^FD{so_date}^FS
^FO620,260^FR^A0N,36,36^FD{total_yards}^FS

^FO10,320^GB790,3,3^FS

^FO10,330^A0N,22,22^FDMachine^FS
^FO120,330^A0N,22,22^FDOper^FS
^FO230,330^A0N,22,22^FDDate/Time^FS
^FO480,330^A0N,22,22^FDYards^FS
^FO10,355^GB790,2,2^FS

{row_zpl}

^XZ"""
        return zpl