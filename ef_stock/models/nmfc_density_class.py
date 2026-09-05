from odoo import api, fields, models


class NmfcDensityClass(models.Model):
    _name = 'nmfc.density.class'
    _description = 'NMFC Density to Freight Class Table'
    _order = 'sequence, density_to desc'

    sequence = fields.Integer('Sequence', default=10)
    name = fields.Char('Class', required=True, help="Freight class, e.g. 50, 77.5, 100")
    density_from = fields.Float('Density From (lbs/f3)', required=True, digits=(12, 2))
    density_to = fields.Float('Density To (lbs/f3)', required=True, digits=(12, 2))
    active = fields.Boolean('Active', default=True)

    _sql_constraints = [
        ('density_range_check',
         'CHECK(density_to >= density_from)',
         'Density To must be greater than or equal to Density From.'),
    ]

    @api.model
    def get_class_from_density(self, density):
        """Return the freight class (Char) whose range contains the given
        density (lbs/ft3), or False if no bracket matches."""
        if not density:
            return False
        line = self.search([
            ('density_from', '<=', density),
            ('density_to', '>=', density),
        ], limit=1)
        return line.name if line else False