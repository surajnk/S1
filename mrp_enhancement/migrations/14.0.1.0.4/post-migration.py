# -*- coding: utf-8 -*-
"""Hand the already-posted input-roll stock moves over to the input lines.

Stock for a final yield line used to be keyed on the parent line
(x_final_roll_line_id). From now on it is keyed on the input line
(x_final_roll_input_id) and the parent no longer posts for lines that have
input lines. Without this step the first edit of a migrated line would find
nothing posted for its input line and consume the whole quantity a second
time.

Only parents with exactly one input line are touched (that is every migrated
line); a line that has several rolls has only ever had input-line moves.
Plain SQL, no stock is moved. Safe to run twice.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        UPDATE stock_move m
           SET x_final_roll_input_id = i.id,
               x_final_roll_line_id = NULL
          FROM final_wo_roll_input i
         WHERE m.x_final_roll_line_id = i.final_roll_id
           AND m.x_final_roll_input_id IS NULL
           AND (SELECT COUNT(*) FROM final_wo_roll_input c
                 WHERE c.final_roll_id = i.final_roll_id) = 1
    """)
    _logger.info("mrp_enhancement: re-pointed %s final roll stock moves to "
                 "their input lines", cr.rowcount)
